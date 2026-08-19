"""Espelho do WhatsApp: adaptador de canal sobre WebSocket.

Entrega ao navegador em vez da Cloud API, mas aceita e produz payloads no
MESMO formato de webhook que a API oficial usa. Trocar em producao e
registrar outra implementacao deste protocolo; o motor nao sabe a
diferenca.

O documento mestre lista "API oficial do WhatsApp" entre o que nao se
constroi no MVP. Esta e a implementacao que ocupa esse lugar sem
distorcer a arquitetura.
"""

import logging

from app.channels.base import DeliveryReceipt, InboundMessage, OutboundMessage
from app.enums import Canal

logger = logging.getLogger(__name__)


class GerenciadorConexoes:
    """Conexoes de espelho abertas, agrupadas por handle.

    Uma pessoa pode ter o espelho aberto mais de uma vez: duas abas, um
    recarregamento em que a conexao antiga ainda nao morreu, ou o modo de
    desenvolvimento do React, que monta o componente duas vezes de
    proposito. Guardar uma unica conexao por handle parecia suficiente e
    nao era: bastava a conexao antiga se registrar DEPOIS da nova (a
    ordem de chegada do handshake nao e garantida) para a resposta ser
    entregue num socket ja morto, e a pessoa ficar olhando o "digitando"
    para sempre.

    Entao aqui cada handle tem uma lista, e a entrega vai para todas as
    conexoes vivas. A que morreu sai da lista sozinha, na primeira falha
    de envio.
    """

    def __init__(self) -> None:
        self._conexoes: dict[str, list] = {}

    def registrar(self, handle: str, websocket) -> None:
        self._conexoes.setdefault(handle, []).append(websocket)

    def remover(self, handle: str, websocket=None) -> None:
        """Tira do ar a conexao que caiu, e so ela.

        Sem o argumento, limpa o handle inteiro. Com ele, remove apenas
        aquele socket: uma sessao que termina nao pode levar junto a
        conexao viva de outra aba.
        """
        if websocket is None:
            self._conexoes.pop(handle, None)
            return

        restantes = [c for c in self._conexoes.get(handle, []) if c is not websocket]
        if restantes:
            self._conexoes[handle] = restantes
        else:
            self._conexoes.pop(handle, None)

    def obter(self, handle: str) -> list:
        return list(self._conexoes.get(handle, []))

    def conectados(self) -> list[str]:
        return list(self._conexoes)


conexoes = GerenciadorConexoes()


class MirrorWhatsAppAdapter:
    """Implementacao de espelho do canal WhatsApp."""

    canal = Canal.WHATSAPP

    def receive(self, raw: dict) -> InboundMessage:
        """Le um payload em formato de webhook da Cloud API.

        A estrutura aninhada nao e capricho: e exatamente a forma que a
        API oficial entrega, e mante-la aqui e o que torna a troca um
        detalhe de implementacao.
        """
        try:
            valor = raw["entry"][0]["changes"][0]["value"]
            mensagem = valor["messages"][0]
            return InboundMessage(
                canal=self.canal,
                handle=mensagem["from"],
                texto=mensagem["text"]["body"],
                contexto=valor.get("metadata", {}),
            )
        except (KeyError, IndexError, TypeError) as erro:
            raise ValueError(f"payload fora do formato de webhook: {erro}") from erro

    def envelopar(self, handle: str, texto: str, contexto: dict | None = None) -> dict:
        """Monta o payload de webhook a partir de uma digitacao no espelho."""
        return {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": contexto or {},
                                "messages": [
                                    {
                                        "from": handle,
                                        "type": "text",
                                        "text": {"body": texto},
                                    }
                                ],
                            },
                        }
                    ]
                }
            ],
        }

    async def send(self, to: str, msg: OutboundMessage) -> DeliveryReceipt:
        abertas = conexoes.obter(to)
        if not abertas:
            # Em producao seria falha de entrega; aqui significa que a
            # aba do espelho foi fechada. Nos dois casos o motor ja
            # persistiu a mensagem, entao nada se perde.
            logger.info("sem espelho conectado para %s", to)
            return DeliveryReceipt(entregue=False, detalhe="sem conexao aberta")

        payload = {
            "tipo": "mensagem",
            "direcao": "saida",
            "texto": msg.texto,
            "acoes_rapidas": msg.acoes_rapidas,
            "fontes": msg.fontes,
        }

        entregues = 0
        for websocket in abertas:
            try:
                await websocket.send_json(payload)
                entregues += 1
            except Exception:  # noqa: BLE001 - o socket morre de varias formas
                # Socket morto que ainda constava na lista. Sai daqui em
                # vez de derrubar a entrega para as outras abas.
                logger.info("conexao morta descartada para %s", to)
                conexoes.remover(to, websocket)

        if not entregues:
            return DeliveryReceipt(entregue=False, detalhe="nenhuma conexao respondeu")
        return DeliveryReceipt(entregue=True)


adaptador = MirrorWhatsAppAdapter()
