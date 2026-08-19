"""Verificacao de ancoragem (secao 5.2, etapa 5).

Se a resposta contiver afirmacao nao sustentada pelas fontes, ela e
BLOQUEADA, nao corrigida, nao suavizada. Bloqueada.

A verificacao roda depois da geracao e nao usa modelo: um modelo que
audita a si mesmo herda os proprios pontos cegos. Aqui a checagem e
mecanica e conservadora, e uma falha dela sempre erra para o lado de
escalar em vez do lado de responder.
"""

import re
import unicodedata
from dataclasses import dataclass, field

from app.llm.base import FONTE_ESTADO

# Numeros, prazos, enderecos e horarios sao o que o sistema nao pode
# inventar: e o que a pessoa vai executar. Uma frase generica errada
# irrita; um prazo errado faz alguem perder o curso.
_PADRAO_NUMERO = re.compile(r"\b\d+(?:[.,]\d+)?\b")
_PADRAO_URL = re.compile(r"(?:https?://|www\.)\S+|\b[\w.-]+\.(?:jus|gov|com|br)\b\S*")
_PADRAO_HORA = re.compile(r"\b\d{1,2}\s*[:h]\s*\d{0,2}\b")


@dataclass(slots=True)
class Ancoragem:
    intacta: bool
    # O que a resposta afirma e as fontes nao sustentam.
    afirmacoes_sem_fonte: list[str] = field(default_factory=list)
    fontes_citadas: list[str] = field(default_factory=list)

    @property
    def motivo(self) -> str:
        if self.intacta:
            return "todas as afirmacoes verificaveis constam nas fontes"
        return "afirmacao nao sustentada pelas fontes: " + ", ".join(
            self.afirmacoes_sem_fonte
        )


def _normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in sem_acento if not unicodedata.combining(c))


def _tokens_verificaveis(texto: str) -> set[str]:
    """Extrai o que precisa constar na fonte para a resposta ser fiel."""
    achados: set[str] = set()
    achados.update(_PADRAO_NUMERO.findall(texto))
    achados.update(m.rstrip(".,;)") for m in _PADRAO_URL.findall(texto))
    achados.update(re.sub(r"\s+", "", m) for m in _PADRAO_HORA.findall(texto))
    return achados


def verificar(
    resposta: str,
    trechos: list[dict],
    fontes_citadas: list[str],
    estado: str = "",
) -> Ancoragem:
    """Confere se a resposta se sustenta nos trechos recuperados.

    `estado` e o resumo do estado individual entregue ao modelo no prompt.
    Ele tambem e lastro legitimo: veio do banco, nao do modelo. Sem isso, o
    numero correto do proprio participante ("9% de progresso") seria tratado
    como invencao e bloquearia a resposta certa.
    """
    if not resposta.strip():
        return Ancoragem(intacta=False, afirmacoes_sem_fonte=["resposta vazia"])

    # O estado individual so e citavel quando de fato foi entregue ao
    # modelo: sem o bloco no prompt, citar essa fonte seria invencao.
    ids_validos = {t["id"] for t in trechos}
    if estado.strip():
        ids_validos.add(FONTE_ESTADO)
    citadas = [f for f in fontes_citadas if f in ids_validos]

    # Sem fonte citada valida, nao ha o que ancorar. Uma resposta que nao
    # aponta de onde veio nao pode carregar o carimbo da Escola.
    if not citadas:
        return Ancoragem(
            intacta=False,
            afirmacoes_sem_fonte=["nenhuma fonte valida citada"],
            fontes_citadas=[],
        )

    # So os trechos efetivamente citados sustentam a resposta. Usar toda a
    # base como lastro deixaria passar afirmacao vinda de outro documento.
    lastro = _normalizar(
        " ".join([t["texto"] for t in trechos if t["id"] in citadas] + [estado])
    )

    sem_fonte = [
        token
        for token in _tokens_verificaveis(resposta)
        if _normalizar(token) not in lastro
    ]

    return Ancoragem(
        intacta=not sem_fonte,
        afirmacoes_sem_fonte=sorted(sem_fonte),
        fontes_citadas=citadas,
    )
