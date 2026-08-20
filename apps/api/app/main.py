import logging
import time

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api import (
    antecipacao,
    atendimento,
    busca,
    canal,
    demo,
    fila,
    governanca,
    radar,
)
from app.config import settings
from app.db import engine
from app.llm import obter_provider
from app.seguranca import (
    METODOS_AUDITADOS,
    ROTAS_COM_CUSTO,
    ConfiguracaoInsegura,
    exigir_admin,
    identificar_ator,
    limitador_geral,
    limitador_llm,
    registrar_requisicao,
    teto_llm,
    verificar_configuracao,
)

logger = logging.getLogger(__name__)

# A documentacao interativa e um mapa completo da superficie de ataque, com
# botao de disparo em cada rota. Util em dev, gratuito para quem sonda em
# producao.
_docs = None if settings.producao else "/docs"

app = FastAPI(
    title="FAROL v2: API",
    description="Fluxo de Atendimento, Resolucao e Orientacao em Laco: SECOEAD/EMERON",
    version="0.1.0",
    docs_url=_docs,
    redoc_url=None if settings.producao else "/redoc",
    openapi_url=None if settings.producao else "/openapi.json",
)


@app.on_event("startup")
def conferir_ambiente() -> None:
    """Ou o ambiente esta seguro quando o servico sobe, ou o servico nao sobe."""
    problemas = verificar_configuracao()
    if not problemas:
        return
    if settings.producao:
        raise ConfiguracaoInsegura(
            "FAROL nao subiu por configuracao insegura:\n  - " + "\n  - ".join(problemas)
        )
    for problema in problemas:
        logger.warning("configuracao: %s", problema)


# Ordem importa: o middleware declarado por ultimo roda primeiro. O de
# seguranca precisa ver a requisicao antes de qualquer coisa gastar recurso.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origens_web,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    # Lista fechada: `*` com credenciais habilitadas devolve qualquer
    # cabecalho que o atacante pedir.
    allow_headers=["Content-Type", "Authorization", "X-Farol-Token"],
    max_age=600,
)

if settings.hosts:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.hosts)


def _recusar(ator: str, request: Request, motivo: str, espera: str) -> JSONResponse:
    """Recusa por excesso, com registro.

    Bloqueio que nao deixa rastro e o pior tipo de bloqueio: no dia
    seguinte ninguem consegue dizer se houve abuso, de onde veio, nem se o
    limite esta calibrado. O 429 entra na trilha como qualquer outra acao.
    """
    if request.method in METODOS_AUDITADOS:
        registrar_requisicao(
            ator=ator,
            metodo=request.method,
            rota=request.url.path,
            status_code=429,
            duracao_ms=0,
            restrita=request.url.path.startswith(("/demo", "/ensaio")),
        )
    return JSONResponse({"detail": motivo}, status_code=429, headers={"Retry-After": espera})


@app.middleware("http")
async def portao(request: Request, call_next):
    """Limite por origem, teto de custo e trilha de auditoria, nesta ordem."""
    ator = identificar_ator(request)
    rota = request.url.path
    inicio = time.perf_counter()

    if not limitador_geral.permitir(ator):
        return _recusar(
            ator, request, "Muitas requisicoes. Tente de novo em um minuto.", espera="60"
        )

    # As rotas que falam com o provedor tem porteiro proprio: sao as unicas
    # em que uma requisicao a mais e dinheiro a menos.
    if rota.startswith(ROTAS_COM_CUSTO) and not limitador_llm.permitir(ator):
        logger.warning("limite de LLM atingido por %s em %s", ator, rota)
        return _recusar(
            ator, request, "Muitas mensagens seguidas. Aguarde alguns segundos.", espera="20"
        )

    resposta = await call_next(request)
    duracao_ms = int((time.perf_counter() - inicio) * 1000)

    # Cabecalhos de defesa do navegador. O front e servido pela mesma
    # origem, entao a politica pode ser restritiva sem quebrar nada.
    resposta.headers["X-Content-Type-Options"] = "nosniff"
    resposta.headers["X-Frame-Options"] = "SAMEORIGIN"
    resposta.headers["Referrer-Policy"] = "same-origin"
    resposta.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    if settings.producao:
        resposta.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

    if request.method in METODOS_AUDITADOS:
        restrita = rota.startswith(("/demo", "/ensaio"))
        registrar_requisicao(
            ator=ator,
            metodo=request.method,
            rota=rota,
            status_code=resposta.status_code,
            duracao_ms=duracao_ms,
            restrita=restrita,
        )

    return resposta


@app.exception_handler(Exception)
async def erro_interno(request: Request, erro: Exception) -> JSONResponse:
    """Erro nao tratado nunca vaza rastro de pilha para o cliente.

    Um traceback publica caminho de arquivo, versao de biblioteca e, no pior
    caso, o trecho de configuracao que causou a falha. O detalhe fica no log
    do servidor, onde a equipe alcanca e o visitante nao.
    """
    logger.exception("erro nao tratado em %s %s", request.method, request.url.path)
    return JSONResponse({"detail": "Erro interno. A equipe foi notificada."}, status_code=500)


app.include_router(busca.router)
app.include_router(atendimento.router)
app.include_router(canal.router)
app.include_router(fila.router)
app.include_router(antecipacao.router)
app.include_router(radar.router)
app.include_router(governanca.router)

# Superficie restrita: o Console move o relogio do mundo e reseta o banco.
# A protecao fica aqui, na inclusao, e nao rota a rota: assim uma rota nova
# no Console nasce protegida em vez de nascer esquecida.
app.include_router(demo.router, dependencies=[Depends(exigir_admin)])


@app.get("/health")
def health() -> dict:
    """Diz a verdade sobre o estado do sistema, inclusive quando degradado."""
    try:
        with engine.connect() as conexao:
            conexao.execute(text("SELECT 1"))
        banco = "ok"
    except Exception as erro:  # noqa: BLE001, health check nunca deve derrubar o processo
        banco = f"erro: {erro.__class__.__name__}"

    provider = obter_provider()
    orcamento = teto_llm.estado
    return {
        "servico": "farol-api",
        "banco": banco,
        "llm": provider.nome,
        # Os dois papeis aparecem separados porque podem divergir: a tela
        # "Como o FAROL decide" (secao 7.3) mostra com que modelo cada
        # etapa rodou, e degradado nao pode passar por normal.
        "modelo_classificacao": settings.llm_model_classificacao,
        "modelo_geracao": settings.llm_model_geracao,
        "degradado": provider.nome == "fallback",
        "embeddings": settings.embedding_provider,
        "canal": settings.channel_adapter,
        "modo_ensaio": settings.modo_ensaio,
        "ambiente": settings.ambiente,
        # Nenhum segredo aqui: so a contagem. Saber quanto do orcamento do
        # dia ja foi gasto e o que permite agir antes de acabar.
        "orcamento_llm": orcamento,
    }
