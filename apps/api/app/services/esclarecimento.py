"""Esclarecimento: "nao entendi" nao e "nao funcionou".

O Contrato de Resolucao (secao 5.5) trata do procedimento que foi tentado
e falhou, e ali a regra e nao repetir. Mas quem escreve "ainda nao
entendi" nao tentou nada: a explicacao e que nao chegou. Escalar isso
direto joga para um servidor um problema que era de redacao, e mandar a
pessoa embora sem resposta e o pior desfecho possivel para quem acabou
de admitir que nao entendeu.

Entao o FAROL reescreve UMA vez, a partir das MESMAS fontes do caso
anterior, em passos curtos. Nao ha nova recuperacao porque o assunto nao
mudou, e nao ha nova busca que "nao entendi" pudesse alimentar.

Na segunda vez, escala. Duas explicacoes que nao chegaram sao um sinal
sobre o texto oficial, nao sobre a pessoa, e e isso que o dossie diz ao
servidor.
"""

import re
import unicodedata

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.enums import ContratoResolucao, SituacaoCaso
from app.models import Caso, Chunk, DocumentoConhecimento, LogAuditoria

# Quantas reescritas antes de admitir que o problema nao e a redacao.
LIMITE_DE_REESCRITAS = 1

ETAPA_AUDITORIA = "reexplicacao"

# Expressoes de incompreensao. Fechadas e deterministicas, como o opt-out:
# o que decide o caminho da conversa nao passa por modelo.
_EXPRESSOES = (
    "nao entendi",
    "nao entendi nada",
    "ainda nao entendi",
    "nao compreendi",
    "nao ficou claro",
    "nao entendi bem",
    "nao consegui entender",
    "como assim",
    "explica melhor",
    "explique melhor",
    "pode explicar melhor",
    "pode explicar de novo",
    "explica de novo",
    "nao entendi essa parte",
    "confuso",
    "ficou confuso",
    "complicado demais",
    "nao sei o que fazer",
    "e agora",
)

# Instrucao acrescentada a geracao. Muda a forma, nunca o conteudo: as
# fontes sao as mesmas, entao a ancoragem continua valendo igual.
_PEDIDO_DE_REESCRITA = (
    "A pessoa leu a explicacao abaixo e respondeu que NAO entendeu. "
    "Reescreva a mesma orientacao, com base exclusivamente nos mesmos "
    "trechos oficiais, em frases curtas, uma acao por linha, com palavras "
    "do dia a dia e sem jargao de sistema. Nao numere os passos: um numero "
    "que nao esta na fonte derruba a ancoragem e bloqueia a resposta. Nao "
    "acrescente informacao nova e nao repita as mesmas frases.\n\n"
    "[Explicacao que nao foi compreendida]\n{resposta}"
)


# --------------------------------------------------------------------------
# O outro lado: quando quem nao entendeu foi o FAROL
# --------------------------------------------------------------------------

# Acima disso a mensagem tem conteudo suficiente para ser uma pergunta de
# verdade, mesmo que o FAROL nao tenha achado fonte para ela. Nesse caso
# escalar e o certo: existe pergunta, e alguem precisa responde-la.
MAXIMO_DE_PALAVRAS_VAGO = 4

PEDIDO_DE_REPETICAO = (
    "Desculpa, não consegui entender. Pode escrever com mais detalhe o que "
    "você precisa? Se for sobre acesso ao AVA, senha, prazo, webconferência "
    "ou certificado, é só dizer."
)


def eh_vaga(texto: str) -> bool:
    """A mensagem e curta demais para o FAROL saber do que se trata?

    Serve para separar dois silencios que hoje terminam no mesmo lugar:
    "nao achei fonte para esta pergunta", que precisa de um servidor, e
    "nao entendi o que voce quis dizer", que so precisa de mais uma frase
    da propria pessoa. Escalar a segunda gasta o tempo de quem atende com
    algo que a pessoa resolveria em cinco segundos.

    So se aplica quando a recuperacao nao trouxe nada: uma mensagem curta
    que encontra fonte ("prazo?") e uma pergunta, e e respondida.
    """
    normalizado = _normalizar(texto)
    if not normalizado:
        return True
    return len(normalizado.split(" ")) <= MAXIMO_DE_PALAVRAS_VAGO


def _normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto.lower())
    limpo = "".join(c for c in sem_acento if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", " ", limpo)).strip()


def eh_incompreensao(texto: str) -> bool:
    """A mensagem diz "a explicacao nao chegou"?

    Conservador de proposito: exige que a mensagem seja SO isso. "nao
    entendi, e o prazo da atividade 3?" carrega uma pergunta nova, e
    pergunta nova vai para o pipeline.
    """
    normalizado = _normalizar(texto)
    return normalizado in _EXPRESSOES


def ultimo_caso_respondido(db: Session, conversa_id) -> Caso | None:
    """O caso que gerou a explicacao que a pessoa nao entendeu."""
    return db.scalar(
        select(Caso)
        .where(Caso.conversa_id == conversa_id)
        .where(Caso.resposta_enviada.is_not(None))
        .where(Caso.situacao == SituacaoCaso.RESPONDIDO)
        .order_by(Caso.criado_em.desc())
    )


def reescritas_ja_feitas(db: Session, caso: Caso) -> int:
    """Conta pelo log de auditoria, que e a fonte de verdade imutavel."""
    return (
        db.scalar(
            select(func.count(LogAuditoria.id))
            .where(LogAuditoria.caso_id == caso.id)
            .where(LogAuditoria.etapa == ETAPA_AUDITORIA)
        )
        or 0
    )


def trechos_do_caso(db: Session, caso: Caso) -> list[dict]:
    """Reconstitui as fontes que sustentaram a resposta anterior.

    Sao elas, e nao uma busca nova: o assunto nao mudou, e "nao entendi"
    nao e texto que sirva de consulta semantica.
    """
    ids = [f["chunk_id"] for f in (caso.fontes_usadas or []) if f.get("chunk_id")]
    if not ids:
        return []

    linhas = db.execute(
        select(Chunk, DocumentoConhecimento)
        .join(DocumentoConhecimento, Chunk.documento_id == DocumentoConhecimento.id)
        .where(Chunk.id.in_(ids))
    ).all()

    return [
        {
            "id": str(chunk.id),
            "texto": chunk.texto,
            "documento": documento.titulo,
            "dono": documento.dono,
            "score": 1.0,
        }
        for chunk, documento in linhas
    ]


def pedido_de_reescrita(resposta_anterior: str) -> str:
    return _PEDIDO_DE_REESCRITA.format(resposta=resposta_anterior)


def marcar_escalado(caso: Caso, dossie_atual: dict) -> None:
    """Segunda incompreensao: o texto oficial e que nao esta funcionando."""
    caso.situacao = SituacaoCaso.ESCALADO
    caso.contrato_resolucao = ContratoResolucao.FALHOU
    caso.orientacao_padrao_falhou = True
    caso.dossie = dossie_atual
