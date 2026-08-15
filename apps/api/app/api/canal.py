"""Endpoints de canal: espelho do WhatsApp e widget do AVA.

O WebSocket entrega ao navegador; o POST aceita o mesmo payload de
webhook que a Cloud API enviaria. Os dois caem no mesmo motor.
"""

import asyncio
import logging

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.channels.base import InboundMessage
from app.channels.mirror import adaptador, conexoes
from app.db import SessionLocal, get_db
from app.enums import Canal
from app.services.conversa import processar

logger = logging.getLogger(__name__)
router = APIRouter(tags=["canais"])

# "Digitando..." tem funcao (secao 12.2, item 11): sem ele, uma resposta
# que demora parece uma resposta que nao veio.
ATRASO_DIGITANDO = 0.4


@router.websocket("/ws/espelho/{handle}")
async def espelho(websocket: WebSocket, handle: str) -> None:
    await websocket.accept()
    conexoes.registrar(handle, websocket)
    logger.info("espelho conectado: %s", handle)

    try:
        while True:
            recebido = await websocket.receive_json()
            texto = (recebido.get("texto") or "").strip()
            if not texto:
                continue

            await websocket.send_json({"tipo": "digitando"})

            # O payload atravessa o formato de webhook mesmo vindo do
            # navegador: e o mesmo caminho que a API oficial usaria.
            envelope = adaptador.envelopar(handle, texto, recebido.get("contexto"))
            entrada = adaptador.receive(envelope)

            try:
                with SessionLocal() as db:
                    saida = await processar(db, entrada)
                    db.commit()
            except Exception:
                logger.exception("falha ao processar mensagem do espelho")
                await websocket.send_json(
                    {
                        "tipo": "mensagem",
                        "direcao": "saida",
                        "texto": (
                            "Tive um problema para processar sua mensagem. "
                            "Pode tentar de novo?"
                        ),
                        "acoes_rapidas": [],
                        "fontes": [],
                    }
                )
                continue

            await asyncio.sleep(ATRASO_DIGITANDO)
            await adaptador.send(handle, saida)

    except WebSocketDisconnect:
        logger.info("espelho desconectado: %s", handle)
    finally:
        conexoes.remover(handle)


class MensagemWidget(BaseModel):
    handle: str = ""
    texto: str = Field(min_length=1, max_length=2000)
    # O widget sabe em que pagina do AVA a pessoa esta.
    pagina: str | None = None


class RespostaWidget(BaseModel):
    texto: str
    acoes_rapidas: list[str]
    fontes: list[dict]


@router.post("/widget/mensagem", response_model=RespostaWidget)
async def widget(
    mensagem: MensagemWidget, db: Session = Depends(get_db)
) -> RespostaWidget:
    entrada = InboundMessage(
        canal=Canal.WIDGET_AVA,
        handle=mensagem.handle,
        texto=mensagem.texto,
        contexto={"pagina": mensagem.pagina} if mensagem.pagina else {},
    )
    saida = await processar(db, entrada)
    db.commit()
    return RespostaWidget(
        texto=saida.texto, acoes_rapidas=saida.acoes_rapidas, fontes=saida.fontes
    )


@router.post("/webhook/whatsapp")
async def webhook(payload: dict, db: Session = Depends(get_db)) -> dict:
    """Recebe no formato da Cloud API.

    Existe para provar que o contrato e o de producao: trocar o espelho
    pela API oficial nao muda nada daqui para dentro.
    """
    entrada = adaptador.receive(payload)
    saida = await processar(db, entrada)
    db.commit()
    recibo = await adaptador.send(entrada.handle, saida)
    return {"entregue": recibo.entregue, "detalhe": recibo.detalhe}
