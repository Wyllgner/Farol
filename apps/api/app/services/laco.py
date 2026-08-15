"""Execucao dos lacos (secao 3).

Nenhuma acao do FAROL termina no envio. Toda acao termina na verificacao
do efeito — e verificar exige alguem passando periodicamente para
conferir. E isso que vive aqui.

O disparo e explicito e idempotente: o Console de Demonstracao chama a
mesma funcao que o agendador chamaria, o que permite avancar o tempo na
apresentacao sem inventar um caminho paralelo so para a demo.
"""

import logging
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.channels.base import OutboundMessage
from app.channels.mirror import adaptador
from app.enums import Canal
from app.models import Conversa
from app.services import contrato

logger = logging.getLogger(__name__)


async def rodar_contratos(db: Session, agora: datetime | None = None) -> dict:
    """Pergunta 'resolveu?' a quem esta no prazo e expira quem nao voltou."""
    agora = agora or datetime.now(UTC)
    perguntados = 0

    for caso in contrato.pendentes_de_pergunta(db, agora):
        texto = contrato.marcar_perguntado(db, caso, agora)
        entregue = await _entregar(db, caso, texto)
        perguntados += 1
        logger.info("contrato perguntado ao caso %s (entregue=%s)", caso.id, entregue)

    expirados = contrato.expirar_sem_retorno(db, agora)
    db.flush()

    return {"perguntados": perguntados, "expirados_sem_retorno": expirados}


async def _entregar(db: Session, caso, texto: str) -> bool:
    """Envia a pergunta pelo canal em que a conversa aconteceu."""
    conversa = db.get(Conversa, caso.conversa_id) if caso.conversa_id else None
    if conversa is None:
        return False

    mensagem = OutboundMessage(
        texto=texto, acoes_rapidas=[contrato.SIM, contrato.NAO]
    )

    from app.enums import Direcao
    from app.services.conversa import registrar_mensagem

    registrar_mensagem(
        db, conversa, Direcao.SAIDA, texto, [contrato.SIM, contrato.NAO]
    )

    # Fora do WhatsApp nao ha entrega ativa nesta fase; a mensagem fica
    # registrada e aparece quando a pessoa voltar ao canal.
    if conversa.canal is not Canal.WHATSAPP:
        return False

    recibo = await adaptador.send(conversa.handle_canal, mensagem)
    return recibo.entregue
