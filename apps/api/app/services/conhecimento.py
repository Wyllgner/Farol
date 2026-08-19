"""Base de conhecimento: chunking, indexacao e recuperacao semantica.

O filtro de vigencia nao e um detalhe de consulta, e a regra da secao 7.2
implementada no unico lugar por onde a recuperacao passa. Uma resposta
desatualizada com carimbo institucional e pior que nenhuma resposta,
porque carrega a autoridade da Escola.
"""

import re
from datetime import UTC, date, datetime

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.llm import obter_provider
from app.models import Chunk, DocumentoConhecimento

# Documentos de orientacao sao curtos. Quebramos por paragrafo e agrupamos
# ate um teto de caracteres, para que cada trecho continue sendo uma unidade
# de sentido: cortar no meio de um procedimento produz fonte inutil.
TETO_CHUNK = 700


def dividir(texto: str, teto: int = TETO_CHUNK) -> list[str]:
    """Divide o texto em trechos que preservam frases inteiras."""
    frases = [f.strip() for f in re.split(r"(?<=[.!?])\s+", texto.strip()) if f.strip()]

    trechos: list[str] = []
    atual = ""
    for frase in frases:
        candidato = f"{atual} {frase}".strip()
        if atual and len(candidato) > teto:
            trechos.append(atual)
            atual = frase
        else:
            atual = candidato
    if atual:
        trechos.append(atual)
    return trechos


async def indexar(db: Session, documento: DocumentoConhecimento) -> int:
    """(Re)indexa um documento. Devolve quantos trechos foram gravados."""
    # Reindexar substitui: trechos orfaos de uma versao antiga continuariam
    # sendo citaveis como fonte oficial.
    for antigo in list(documento.chunks):
        db.delete(antigo)
    db.flush()

    textos = dividir(documento.conteudo)
    if not textos:
        return 0

    vetores = await obter_provider().embutir(textos)
    for ordem, (trecho, vetor) in enumerate(zip(textos, vetores, strict=True)):
        # Anexar pela relacao, e nao com db.add solto: assim o documento
        # ja sai daqui citavel na mesma sessao, sem depender de recarga.
        documento.chunks.append(
            Chunk(ordem=ordem, texto=trecho, vetor=vetor)
        )

    db.flush()
    return len(textos)


def _vigente(hoje: date):
    """Condicao SQL de fonte utilizavel: vigente e dentro da validade."""
    return (DocumentoConhecimento.situacao == "vigente") & (
        (DocumentoConhecimento.valido_ate.is_(None))
        | (DocumentoConhecimento.valido_ate >= hoje)
    )


async def buscar(
    db: Session,
    pergunta: str,
    limite: int = 4,
    distancia_maxima: float = 0.65,
) -> list[dict]:
    """Recupera trechos oficiais relevantes e vigentes.

    Fonte vencida, rebaixada ou em revisao nunca entra: sem fonte valida
    e vigente, o FAROL escala em vez de responder.
    """
    vetor = (await obter_provider().embutir([pergunta]))[0]
    hoje = datetime.now(UTC).date()

    distancia = Chunk.vetor.cosine_distance(vetor).label("distancia")
    consulta = (
        select(Chunk, DocumentoConhecimento, distancia)
        .join(DocumentoConhecimento, Chunk.documento_id == DocumentoConhecimento.id)
        .where(_vigente(hoje))
        .where(Chunk.vetor.is_not(None))
        .order_by(distancia)
        .limit(limite)
    )

    resultados = []
    for chunk, documento, dist in db.execute(consulta).all():
        # Um trecho semanticamente distante nao "quase serve": ele nao
        # sustenta a resposta, e passa-lo adiante convida a extrapolacao.
        if dist > distancia_maxima:
            continue
        resultados.append(
            {
                "id": str(chunk.id),
                "texto": chunk.texto,
                "documento": documento.titulo,
                "dono": documento.dono,
                "valido_ate": documento.valido_ate.isoformat()
                if documento.valido_ate
                else None,
                # Score legivel: 1.0 = identico, 0.0 = sem relacao.
                "score": round(1 - float(dist), 4),
            }
        )

    if resultados:
        _marcar_citacao(db, {r["documento"] for r in resultados})
    return resultados


def _marcar_citacao(db: Session, titulos: set[str]) -> None:
    """Registra o uso da fonte: alimenta a curadoria dos 90 dias (F31)."""
    db.execute(
        text(
            "UPDATE documento_conhecimento SET ultima_citacao = now() "
            "WHERE titulo = ANY(:titulos)"
        ),
        {"titulos": list(titulos)},
    )
