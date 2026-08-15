"""Contrato de canal (secao 10).

O motor recebe InboundMessage e devolve OutboundMessage. Ele nao conhece
canal: adicionar um canal nao duplica logica, e trocar a implementacao do
WhatsApp por a API oficial nao toca uma linha do motor.

Os payloads seguem o formato de webhook da Cloud API de proposito. A
camada de espelho nao e um atalho — e a arquitetura correta com
implementacao trocavel, e o formato e a parte que prova isso.
"""

from dataclasses import dataclass, field
from typing import Protocol

from app.enums import Canal


@dataclass(slots=True)
class InboundMessage:
    canal: Canal
    # Identificador do interlocutor no canal: telefone, e-mail, sessao.
    handle: str
    texto: str
    # Contexto extra que o canal conhece e o motor pode usar — o widget
    # do AVA sabe em que pagina a pessoa esta.
    contexto: dict = field(default_factory=dict)


@dataclass(slots=True)
class OutboundMessage:
    texto: str
    # No maximo uma acao principal e um escape (secao 12.2, item 2).
    acoes_rapidas: list[str] = field(default_factory=list)
    # Fontes exibidas junto da resposta (secao 12.2, item 6).
    fontes: list[dict] = field(default_factory=list)


@dataclass(slots=True)
class DeliveryReceipt:
    entregue: bool
    detalhe: str = ""


class ChannelAdapter(Protocol):
    canal: Canal

    async def send(self, to: str, msg: OutboundMessage) -> DeliveryReceipt: ...

    def receive(self, raw: dict) -> InboundMessage: ...
