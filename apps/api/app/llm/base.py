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
    # A mensagem trata de assunto da Escola? False so quando o modelo tem
    # certeza de que nao. O padrao e True porque a duvida tem que ir para
    # o caminho que termina em atendimento humano, nunca em recusa.
    no_escopo: bool = True


# Fonte citavel que nao e um trecho da base: o estado individual do
# participante, lido do banco. "Voce esta no curso X e faltam 15 dias" nao
# consta em documento nenhum, e ainda assim e a afirmacao mais verificavel
# que o sistema pode fazer. Sem isto, toda pergunta sobre o proprio caso
# escalava por falta de fonte, que e justamente o que o Andar 2 promete
# responder.
FONTE_ESTADO = "estado-do-participante"


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
