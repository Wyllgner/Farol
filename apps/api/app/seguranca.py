"""Camada de seguranca: segredos, acesso restrito, teto de custo e trilha.

Tres ameacas concretas guiam este modulo, nesta ordem:

1. **A chave do provedor de LLM.** Ela nunca chega ao navegador, nunca entra
   no repositorio e nunca aparece em log ou resposta de erro. O maior risco
   real nao e o vazamento, e o **abuso**: as rotas de atendimento e busca
   gastam creditos a cada chamada, e uma URL publica sem defesa e um cartao
   de credito aberto. Por isso ha limite por origem e teto diario, e o teto
   degrada para o fallback deterministico em vez de derrubar o servico.

2. **As superficies que nao sao para o publico.** O Console de Demonstracao
   controla o mundo (avanca o relogio, reseta o banco) e a tela "Como o FAROL
   decide" libera categorias do Modo Ensaio. As duas exigem token.

3. **Saber quem fez o que.** Em ambiente judiciario rastreabilidade nao e
   recurso, e requisito. Toda requisicao que muda estado entra no log
   append-only, com ator, rota, resultado e duracao.
"""

import hashlib
import hmac
import logging
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from threading import Lock

from fastapi import Header, HTTPException, Request, status

from app.config import settings

logger = logging.getLogger(__name__)

CABECALHO_TOKEN = "X-Farol-Token"


# --------------------------------------------------------------------------
# Segredos
# --------------------------------------------------------------------------


def mascarar(segredo: str | None) -> str:
    """Forma segura de citar um segredo em log: prova posse sem revelar.

    Guarda os quatro ultimos caracteres porque e o suficiente para conferir
    *qual* chave esta em uso quando ha mais de um ambiente, e insuficiente
    para reconstruir qualquer coisa.
    """
    if not segredo:
        return "(vazio)"
    if len(segredo) <= 8:
        return "***"
    return f"{segredo[:3]}...{segredo[-4:]} ({len(segredo)} car.)"


class ConfiguracaoInsegura(RuntimeError):
    """Erro de partida. Falhar no boot e melhor que subir exposto."""


def verificar_configuracao() -> list[str]:
    """Roda uma vez na partida. Em producao, erro aqui impede o processo de subir.

    A regra de ouro: nada nesta funcao pode ser resolvido em tempo de
    execucao. Ou o ambiente esta correto quando o servico sobe, ou o
    servico nao sobe. Configuracao insegura que "so vamos arrumar depois"
    e exatamente a que fica.
    """
    problemas: list[str] = []

    if settings.producao:
        if not settings.admin_token:
            problemas.append(
                "FAROL_ADMIN_TOKEN vazio: o Console e a tela Como decide ficariam "
                "abertos na internet. Gere um com: python -c "
                '"import secrets; print(secrets.token_urlsafe(32))"'
            )
        elif len(settings.admin_token) < 24:
            problemas.append(
                f"FAROL_ADMIN_TOKEN curto demais ({len(settings.admin_token)} caracteres): "
                "use ao menos 24 para nao ser adivinhavel por forca bruta."
            )

        for origem in settings.origens_web:
            if origem.startswith("http://") and "localhost" not in origem:
                problemas.append(
                    f"WEB_ORIGIN em texto claro: {origem}. Em producao a origem "
                    "precisa ser https, ou o token do administrador trafega exposto."
                )

        if "*" in settings.origens_web:
            problemas.append("WEB_ORIGIN='*' com credenciais habilitadas: combinacao proibida.")

    # Vale nos dois ambientes: dizer que usa OpenAI sem chave nao e um erro
    # fatal (o motor cai no fallback), mas silencio aqui vira "por que a
    # resposta ficou burra?" no meio da apresentacao.
    if settings.llm_provider in {"openai", "anthropic"}:
        chave = (
            settings.openai_api_key
            if settings.llm_provider == "openai"
            else settings.anthropic_api_key
        )
        if not chave:
            logger.warning(
                "LLM_PROVIDER=%s sem chave: o motor vai operar em modo degradado "
                "(fallback deterministico).",
                settings.llm_provider,
            )
        else:
            logger.info("LLM_PROVIDER=%s, chave %s", settings.llm_provider, mascarar(chave))

    return problemas


# --------------------------------------------------------------------------
# Acesso restrito
# --------------------------------------------------------------------------


def identificar_ator(request: Request) -> str:
    """Quem esta do outro lado, sem guardar dado pessoal.

    O IP nao e gravado em texto claro: entra no log como hash truncado.
    Isso preserva o que a auditoria precisa (distinguir e correlacionar
    atores, contar reincidencia) e descarta o que ela nao precisa
    (identificar a pessoa fisica). LGPD por construcao, nao por promessa.
    """
    encaminhado = request.headers.get("x-forwarded-for", "")
    bruto = encaminhado.split(",")[0].strip() if encaminhado else (
        request.client.host if request.client else "desconhecido"
    )
    digest = hashlib.sha256(f"{bruto}{settings.sal_auditoria}".encode()).hexdigest()
    return f"anon:{digest[:12]}"


def token_valido(recebido: str | None) -> bool:
    """Comparacao em tempo constante: `==` vaza o tamanho do prefixo correto."""
    if not settings.admin_token or not recebido:
        return False
    return hmac.compare_digest(recebido, settings.admin_token)


async def exigir_admin(
    request: Request,
    x_farol_token: str | None = Header(default=None, alias=CABECALHO_TOKEN),
) -> str:
    """Dependencia das superficies restritas: Console e Como decide.

    Fora de producao com token vazio, libera: exigir segredo para rodar
    `make dev` empurraria a equipe a inventar um token fraco e fixo, que e
    pior do que nao ter. Em producao o boot ja garantiu que existe.
    """
    if not settings.producao and not settings.admin_token:
        return "dev:aberto"

    if not token_valido(x_farol_token):
        registrar_tentativa_negada(request)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Superficie restrita. Informe um token valido.",
            headers={"WWW-Authenticate": CABECALHO_TOKEN},
        )
    return "admin"


# --------------------------------------------------------------------------
# Limite por origem e teto de custo
# --------------------------------------------------------------------------


@dataclass
class _Janela:
    """Janela deslizante por ator. Em memoria de proposito.

    Uma instancia unica e o desenho previsto; se um dia houver mais de uma,
    a contagem precisa migrar para o Redis, e este comentario e o aviso.
    """

    marcas: deque[float] = field(default_factory=deque)


class LimitadorDeTaxa:
    def __init__(self, limite: int, janela_segundos: int) -> None:
        self.limite = limite
        self.janela = janela_segundos
        self._atores: dict[str, _Janela] = {}
        self._trava = Lock()

    def permitir(self, ator: str) -> bool:
        agora = time.monotonic()
        with self._trava:
            janela = self._atores.setdefault(ator, _Janela())
            while janela.marcas and agora - janela.marcas[0] > self.janela:
                janela.marcas.popleft()
            if len(janela.marcas) >= self.limite:
                return False
            janela.marcas.append(agora)

            # Higiene: sem isto, um ataque distribuido faz o dicionario
            # crescer ate o processo morrer, transformando a defesa em
            # vetor de negacao de servico.
            if len(self._atores) > 10_000:
                self._atores = {
                    chave: valor for chave, valor in self._atores.items() if valor.marcas
                }
            return True


limitador_geral = LimitadorDeTaxa(settings.limite_req_min, 60)
limitador_llm = LimitadorDeTaxa(settings.limite_llm_min, 60)

# Rotas que custam dinheiro a cada chamada: sao as que chamam o provedor.
ROTAS_COM_CUSTO = ("/atendimento", "/search", "/widget/mensagem", "/webhook/whatsapp")


class TetoDeCusto:
    """Orcamento diario de chamadas ao provedor.

    Estourar o teto **nao** derruba o FAROL: ele passa a responder pelo
    fallback deterministico. A escolha e deliberada e coerente com a tese
    do produto: degradar com honestidade (o `/health` mostra) e melhor que
    ficar mudo, e infinitamente melhor que zerar o credito da instituicao.
    """

    def __init__(self, teto: int) -> None:
        self.teto = teto
        self._dia: date = datetime.now(UTC).date()
        self._gastas = 0
        self._trava = Lock()

    def consumir(self) -> bool:
        with self._trava:
            hoje = datetime.now(UTC).date()
            if hoje != self._dia:
                self._dia, self._gastas = hoje, 0
            if self.teto and self._gastas >= self.teto:
                return False
            self._gastas += 1
            return True

    @property
    def estado(self) -> dict:
        return {"teto_diario": self.teto, "gastas_hoje": self._gastas}


teto_llm = TetoDeCusto(settings.teto_llm_dia)


# --------------------------------------------------------------------------
# Trilha de auditoria das requisicoes
# --------------------------------------------------------------------------

# Rotas de leitura pura e ruidosas nao entram no log: auditoria que registra
# tudo vira palheiro, e palheiro nao e auditoria.
METODOS_AUDITADOS = {"POST", "PUT", "PATCH", "DELETE"}


def registrar_requisicao(
    ator: str,
    metodo: str,
    rota: str,
    status_code: int,
    duracao_ms: int,
    restrita: bool,
) -> None:
    """Grava a requisicao na tabela append-only, em sessao propria.

    Sessao separada de proposito: a transacao do atendimento pode ter sido
    revertida por erro, e justamente esse caso e o que a auditoria mais
    precisa registrar.
    """
    from app.db import SessionLocal
    from app.models import LogAuditoria

    try:
        with SessionLocal() as db:
            db.add(
                LogAuditoria(
                    caso_id=None,
                    etapa="requisicao",
                    payload={
                        "ator": ator,
                        "metodo": metodo,
                        "rota": rota,
                        "status": status_code,
                        "duracao_ms": duracao_ms,
                        "superficie": "restrita" if restrita else "publica",
                        "quando": datetime.now(UTC).isoformat(),
                    },
                )
            )
            db.commit()
    except Exception:  # auditoria nunca derruba o atendimento
        logger.exception("falha ao registrar auditoria da rota %s", rota)


def registrar_tentativa_negada(request: Request) -> None:
    """Token errado e o evento mais interessante do log: alguem tentou entrar."""
    ator = identificar_ator(request)
    logger.warning("acesso negado a %s por %s", request.url.path, ator)
    registrar_requisicao(
        ator=ator,
        metodo=request.method,
        rota=request.url.path,
        status_code=401,
        duracao_ms=0,
        restrita=True,
    )


def novo_id_correlacao() -> str:
    return uuid.uuid4().hex[:16]
