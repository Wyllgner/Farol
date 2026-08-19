"""Entrega diferida: a fronteira entre enviar e chegar.

O motor de antecipacao decide interromper alguem e monta a mensagem. Isso
NAO e uma entrega. A mensagem chega quando o canal a coloca na frente da
pessoa: o espelho abre, o widget do AVA carrega, a Cloud API confirma o
recebimento. Ate la ela fica na fila.

A distincao nao e purismo. O Andar 1 inteiro se apoia na hipotese "avisei,
e por isso o atendimento nao aconteceu". Contar essa hipotese a partir do
momento em que a mensagem foi *montada* credita ao gatilho um efeito que
ele nao teve: a pessoa nao abriu chamado porque nao viu nada, nao porque
foi ajudada. E como o desligamento automatico de gatilho e derivado dessa
medicao, o erro nao ficava so no painel, ele mudava o comportamento do
motor.

Por isso o relogio da verificacao comeca aqui, e nao antes.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enums import Canal, Direcao
from app.models import Conversa, EventoProativo, Mensagem, Participante
from app.services import atencao, auditoria
from app.services.gatilhos import carregar


def pendentes(db: Session, canal: Canal, handle: str) -> list[Mensagem]:
    """Mensagens que existem para esta pessoa e ainda nao chegaram."""
    return list(
        db.scalars(
            select(Mensagem)
            .join(Conversa, Mensagem.conversa_id == Conversa.id)
            .where(Conversa.canal == canal)
            .where(Conversa.handle_canal == handle)
            .where(Mensagem.direcao == Direcao.SAIDA)
            .where(Mensagem.entregue_em.is_(None))
            .order_by(Mensagem.criado_em)
        ).all()
    )


def confirmar(
    db: Session, mensagens: list[Mensagem], agora: datetime | None = None
) -> int:
    """Marca como entregue e inicia o que depende da entrega.

    O que depende dela: o debito no orcamento de atencao (interromper so
    custa quando de fato interrompe) e o relogio da hipotese.
    """
    if not mensagens:
        return 0

    agora = agora or datetime.now(UTC)
    for mensagem in mensagens:
        mensagem.entregue_em = agora
        if mensagem.evento_proativo_id is not None:
            evento = db.get(EventoProativo, mensagem.evento_proativo_id)
            if evento is not None and evento.enviado_em is None:
                iniciar_hipotese(db, evento, agora)

    db.flush()
    return len(mensagens)


def iniciar_hipotese(db: Session, evento: EventoProativo, agora: datetime) -> None:
    """Da o start no relogio da hipotese, no instante da entrega.

    Publica porque "a mensagem chegou" e um fato que outros canais vao
    precisar afirmar: cada adaptador confirma a entrega do seu jeito, e
    todos passam por aqui.
    """
    regras = carregar()
    evento.enviado_em = agora
    evento.verificar_em = agora + timedelta(days=regras.janela_dias)

    participante = db.get(Participante, evento.participante_id)
    if participante is not None:
        atencao.debitar(db, participante)

    auditoria.registrar(
        db,
        "mensagem_proativa_entregue",
        {
            "gatilho": evento.gatilho,
            "hipotese": evento.hipotese,
            "verificar_em": evento.verificar_em.isoformat(),
        },
    )


def na_fila(db: Session, canal: Canal | None = None) -> int:
    """Quantas mensagens aguardam entrega. Alimenta o painel do Andar 1."""
    consulta = (
        select(Mensagem.id)
        .join(Conversa, Mensagem.conversa_id == Conversa.id)
        .where(Mensagem.direcao == Direcao.SAIDA)
        .where(Mensagem.entregue_em.is_(None))
    )
    if canal is not None:
        consulta = consulta.where(Conversa.canal == canal)
    return len(db.scalars(consulta).all())
