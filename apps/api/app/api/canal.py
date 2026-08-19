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
from app.services import entrega
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

    # A mensagem proativa pode ter sido montada com a aba fechada. Ela
    # espera na fila e chega quando a pessoa abre o WhatsApp, que e o que
    # acontece no aparelho de verdade. So agora ela conta como entregue.
    with SessionLocal() as db:
        fila_inicial = entrega.pendentes(db, Canal.WHATSAPP, handle)
        for mensagem in fila_inicial:
            await websocket.send_json(
                {
                    "tipo": "mensagem",
                    "direcao": "saida",
                    "texto": mensagem.conteudo,
                    "acoes_rapidas": mensagem.acoes_rapidas,
                    "fontes": [],
                }
            )
        entrega.confirmar(db, fila_inicial)
        db.commit()

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
        conexoes.remover(handle, websocket)


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


class MensagemPendente(BaseModel):
    texto: str
    acoes_rapidas: list[str]


@router.get("/widget/pendentes", response_model=list[MensagemPendente])
def pendentes_do_widget(
    handle: str = "", db: Session = Depends(get_db)
) -> list[MensagemPendente]:
    """Mensagens proativas que esperavam a pessoa abrir o AVA.

    O widget nao tem conexao permanente: ele pergunta ao carregar. Este
    e o momento da entrega no canal do AVA, e e daqui que a hipotese
    daquela mensagem passa a contar o prazo.
    """
    fila = entrega.pendentes(db, Canal.WIDGET_AVA, handle)
    resposta = [
        MensagemPendente(texto=m.conteudo, acoes_rapidas=m.acoes_rapidas) for m in fila
    ]
    entrega.confirmar(db, fila)
    db.commit()
    return resposta


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
