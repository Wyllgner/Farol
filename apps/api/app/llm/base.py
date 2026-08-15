"""Contrato de provedor de LLM.

Arquitetura agnostica de provedor (secao 17, mitigacao do risco de dependencia
de API externa). O motor conversa com este protocolo, nunca com um SDK.
"""

from dataclasses import dataclass, field
from typing import Protocol

from app.enums import Categoria


@dataclass(slots=True)
class Classificacao:
    categoria: Categoria
    confianca: float
    # True quando a classificacao veio do fallback deterministico.
    # A tela "Como o FAROL decide" expoe isso: o sistema nao esconde
    # quando esta operando degradado.
    degradado: bool = False


@dataclass(slots=True)
class RespostaAncorada:
    texto: str
    # Ids dos chunks que sustentam a resposta. Vazio == NAO_SEI.
    fontes: list[str] = field(default_factory=list)
    nao_sei: bool = False


class LLMProvider(Protocol):
    nome: str

    async def classificar(self, texto: str) -> Classificacao: ...

    async def gerar_ancorado(self, pergunta: str, trechos: list[dict]) -> RespostaAncorada: ...

    async def embutir(self, textos: list[str]) -> list[list[float]]: ...
