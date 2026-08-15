"""Espelho do WhatsApp — adaptador de canal sobre WebSocket.

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
    """Conexoes abertas por handle. Uma pessoa, uma sessao de espelho."""

    def __init__(self) -> None:
        self._conexoes: dict[str, object] = {}

    def registrar(self, handle: str, websocket) -> None:
        self._conexoes[handle] = websocket

    def remover(self, handle: str) -> None:
        self._conexoes.pop(handle, None)

    def obter(self, handle: str):
        return self._conexoes.get(handle)

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
        websocket = conexoes.obter(to)
        if websocket is None:
            # Em producao seria falha de entrega; aqui significa que a
            # aba do espelho foi fechada. Nos dois casos o motor ja
            # persistiu a mensagem, entao nada se perde.
            logger.info("sem espelho conectado para %s", to)
            return DeliveryReceipt(entregue=False, detalhe="sem conexao aberta")

        await websocket.send_json(
            {
                "tipo": "mensagem",
                "direcao": "saida",
                "texto": msg.texto,
                "acoes_rapidas": msg.acoes_rapidas,
                "fontes": msg.fontes,
            }
        )
        return DeliveryReceipt(entregue=True)


adaptador = MirrorWhatsAppAdapter()
