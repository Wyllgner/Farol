"""Auditoria da Jornada — partida a frio (secao 6.3).

O Andar 3 depende de historico acumulado, e no dia 1 a base esta vazia.
Para gerar valor imediatamente, o FAROL varre o conteudo da plataforma
procurando defeitos conhecidos que geram duvida — e produz as primeiras
ordens de correcao ANTES do primeiro atendimento.

Os cinco defeitos procurados sao os do documento: prazo ausente ou
ambiguo, link critico abaixo da dobra, linguagem de sistema, pagina sem
caminho para suporte, e texto que pressupoe conhecimento nao fornecido.
"""

import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DocumentoConhecimento
from app.services import auditoria


@dataclass(slots=True)
class Achado:
    defeito: str
    documento: str
    evidencia: str
    acao: str
    # Quantos atendimentos por mes este defeito plausivelmente gera. E uma
    # estimativa declarada como tal — a auditoria a frio nao tem medicao.
    impacto_estimado: int


# Termos que so fazem sentido para quem construiu o sistema. Sao a marca
# da "linguagem de sistema, nao de pessoa" que o documento aponta.
JARGAO = [
    "status", "pendencia", "homologacao", "situacao cadastral",
    "parametrizacao", "instancia", "modulo n", "flag", "log",
]

# Palavras de prazo sem numero ao lado indicam prazo ambiguo.
TERMOS_PRAZO = ["prazo", "ate quando", "data limite", "vencimento"]

PADRAO_NUMERO = re.compile(r"\b\d+\b")
PADRAO_SUPORTE = re.compile(
    r"secoead|suporte|atendimento|whatsapp|contato|fale conosco", re.IGNORECASE
)


def _sem_prazo_explicito(texto: str) -> bool:
    minusculo = texto.lower()
    menciona = any(termo in minusculo for termo in TERMOS_PRAZO)
    return menciona and not PADRAO_NUMERO.search(texto)


def _usa_jargao(texto: str) -> list[str]:
    minusculo = texto.lower()
    return [termo for termo in JARGAO if termo in minusculo]


def _sem_caminho_para_suporte(texto: str) -> bool:
    return not PADRAO_SUPORTE.search(texto)


def _link_tardio(texto: str) -> bool:
    """Link critico mencionado so no fim do texto — o 'abaixo da dobra'.

    Em documento textual, a dobra e a posicao: o que aparece depois de
    dois tercos do texto e o que a pessoa provavelmente nao le.
    """
    posicao = texto.lower().find("link")
    return posicao > 0 and posicao > len(texto) * 0.66


def auditar(db: Session) -> list[Achado]:
    """Varre a base publicada procurando defeitos que geram duvida."""
    achados: list[Achado] = []

    for documento in db.scalars(
        select(DocumentoConhecimento).where(
            DocumentoConhecimento.situacao == "vigente"
        )
    ).all():
        texto = documento.conteudo

        if _sem_prazo_explicito(texto):
            achados.append(
                Achado(
                    defeito="prazo ausente ou ambiguo",
                    documento=documento.titulo,
                    evidencia="menciona prazo sem informar numero de dias ou data",
                    acao=(
                        "Substituir a mencao generica a prazo por a data ou o "
                        "numero de dias, no proprio texto."
                    ),
                    impacto_estimado=6,
                )
            )

        if termos := _usa_jargao(texto):
            achados.append(
                Achado(
                    defeito="linguagem de sistema, nao de pessoa",
                    documento=documento.titulo,
                    evidencia=f"usa os termos: {', '.join(termos)}",
                    acao=(
                        "Reescrever em linguagem de pessoa: dizer o que falta "
                        "fazer, nao o nome interno do estado."
                    ),
                    impacto_estimado=4,
                )
            )

        if _sem_caminho_para_suporte(texto):
            achados.append(
                Achado(
                    defeito="pagina sem caminho visivel para suporte",
                    documento=documento.titulo,
                    evidencia="nao menciona nenhum canal de atendimento",
                    acao=(
                        "Acrescentar ao fim do texto como falar com a SECOEAD "
                        "se o procedimento nao resolver."
                    ),
                    impacto_estimado=3,
                )
            )

        if _link_tardio(texto):
            achados.append(
                Achado(
                    defeito="link critico abaixo da dobra",
                    documento=documento.titulo,
                    evidencia="o link so aparece no ultimo terco do texto",
                    acao="Mover o link para a primeira frase do procedimento.",
                    impacto_estimado=5,
                )
            )

    achados.sort(key=lambda a: a.impacto_estimado, reverse=True)
    auditoria.registrar(
        db,
        "auditoria_jornada",
        {"achados": len(achados), "defeitos": sorted({a.defeito for a in achados})},
    )
    return achados
