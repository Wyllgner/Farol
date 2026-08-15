"""Andar 1 — ANTECIPAR (secao 4).

Percorre as matriculas, avalia os gatilhos ativos, deixa o orcamento de
atencao decidir o que merece a interrupcao, envia e registra a hipotese
que sera verificada depois.

A ordem importa: avaliamos todos os candidatos de uma pessoa ANTES de
gastar saldo, para que o saldo va para a mensagem de maior valor — e nao
para a primeira que passou no filtro.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.channels.base import OutboundMessage
from app.channels.mirror import adaptador
from app.enums import Canal, Direcao
from app.models import Matricula, Participante
from app.services import atencao, auditoria, gatilhos
from app.services.conversa import obter_ou_criar, registrar_mensagem
from app.services.gatilhos import Gatilho

logger = logging.getLogger(__name__)

@dataclass(slots=True)
class Candidata:
    matricula: Matricula
    gatilho: Gatilho
    valor: float


async def rodar(db: Session, agora: datetime | None = None) -> dict:
    """Uma passada completa do motor de antecipacao."""
    agora = agora or datetime.now(UTC)
    regras = gatilhos.carregar()

    ativos: list[Gatilho] = []
    desativados: dict[str, str] = {}
    for gatilho in regras.gatilhos:
        ligado, motivo = atencao.esta_ativo(db, gatilho)
        (ativos.append(gatilho) if ligado else desativados.update({gatilho.chave: motivo}))

    enviados: dict[str, int] = {}
    barrados: dict[str, int] = {}

    for participante in db.scalars(select(Participante)).all():
        candidatas = _candidatas(db, participante, ativos, agora)
        if not candidatas:
            continue

        # Gasta o orcamento na de maior valor esperado, nao na primeira.
        melhor = max(candidatas, key=lambda c: c.valor)
        autorizado, motivo = atencao.pode_interromper(
            db, participante, melhor.gatilho, melhor.valor
        )

        if not autorizado:
            barrados[motivo] = barrados.get(motivo, 0) + 1
            continue

        await _enviar(db, participante, melhor, agora)
        enviados[melhor.gatilho.chave] = enviados.get(melhor.gatilho.chave, 0) + 1

    db.flush()
    return {
        "enviados": enviados,
        "total_enviado": sum(enviados.values()),
        "barrados_pelo_orcamento": barrados,
        "gatilhos_desativados": desativados,
    }


def _candidatas(
    db: Session, participante: Participante, ativos: list[Gatilho], agora: datetime
) -> list[Candidata]:
    matriculas = db.scalars(
        select(Matricula).where(Matricula.participante_id == participante.id)
    ).all()

    candidatas = []
    for matricula in matriculas:
        for gatilho in ativos:
            if not gatilhos.avaliar(gatilho, matricula, agora):
                continue
            medida = atencao.efetividade(db, gatilho.chave)
            candidatas.append(
                Candidata(
                    matricula=matricula,
                    gatilho=gatilho,
                    valor=atencao.valor_esperado(gatilho, medida.taxa),
                )
            )
    return candidatas


async def _enviar(
    db: Session, participante: Participante, candidata: Candidata, agora: datetime
) -> None:
    texto = gatilhos.montar_mensagem(candidata.gatilho, candidata.matricula, agora)
    canal = participante.canal_preferido or Canal.WHATSAPP
    handle = (
        participante.telefone if canal is Canal.WHATSAPP else participante.email
    ) or ""

    conversa = obter_ou_criar(db, canal, handle)
    registrar_mensagem(db, conversa, Direcao.SAIDA, texto, candidata.gatilho.acoes)

    atencao.debitar(db, participante)
    evento = atencao.registrar_hipotese(
        db, participante, candidata.gatilho, candidata.valor, agora
    )

    auditoria.registrar(
        db,
        "mensagem_proativa",
        {
            "gatilho": candidata.gatilho.chave,
            "valor_esperado": candidata.valor,
            "hipotese": evento.hipotese,
            "verificar_em": evento.verificar_em.isoformat(),
        },
    )

    if canal is Canal.WHATSAPP:
        await adaptador.send(
            handle,
            OutboundMessage(texto=texto, acoes_rapidas=candidata.gatilho.acoes),
        )


def painel(db: Session) -> list[dict]:
    """Estado de cada gatilho, para a tela de transparencia."""
    linhas = []
    for gatilho in gatilhos.carregar().gatilhos:
        medida = atencao.efetividade(db, gatilho.chave)
        ligado, motivo = atencao.esta_ativo(db, gatilho)
        linhas.append(
            {
                "chave": gatilho.chave,
                "titulo": gatilho.titulo,
                "ativo": ligado,
                "motivo": motivo,
                "enviados": medida.amostra + medida.pendentes,
                "confirmados": medida.confirmados,
                "refutados": medida.refutados,
                "pendentes": medida.pendentes,
                "antecipacao_efetiva": medida.taxa,
                "valor_esperado": atencao.valor_esperado(gatilho, medida.taxa),
            }
        )
    return linhas
