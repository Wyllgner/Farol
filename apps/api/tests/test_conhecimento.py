"""Testes da base de conhecimento.

Rodam sem rede: o vetor da pergunta e substituido pelo vetor de um trecho
ja indexado, o que garante que aquele trecho seria o melhor resultado
possivel. E o cenario mais dificil para o filtro de vigencia — se ele
exclui a fonte que casaria perfeitamente, exclui qualquer outra.
"""

import pytest
from sqlalchemy import select

from app.db import SessionLocal
from app.models import Chunk, DocumentoConhecimento
from app.services import conhecimento
from app.services.conhecimento import buscar, dividir


class _ProviderFalso:
    """Devolve sempre o mesmo vetor, sem chamar API nenhuma."""

    nome = "teste"

    def __init__(self, vetor: list[float]) -> None:
        self._vetor = vetor

    async def embutir(self, textos: list[str]) -> list[list[float]]:
        return [self._vetor for _ in textos]


@pytest.fixture
def db():
    with SessionLocal() as sessao:
        yield sessao
        sessao.rollback()


# --------------------------------------------------------------------------
# Chunking
# --------------------------------------------------------------------------


def test_dividir_preserva_frases_inteiras():
    texto = "Primeira frase. Segunda frase! Terceira frase?"
    assert dividir(texto, teto=1000) == [texto]


def test_dividir_quebra_sem_cortar_frase():
    frase = "Uma frase de tamanho conhecido para o teste."
    trechos = dividir(" ".join([frase] * 6), teto=100)

    assert len(trechos) > 1
    # Cortar no meio de um procedimento produz fonte inutil.
    for trecho in trechos:
        assert trecho.endswith((".", "!", "?"))


def test_dividir_texto_vazio():
    assert dividir("   ") == []


# --------------------------------------------------------------------------
# Vigencia — a regra da secao 7.2
# --------------------------------------------------------------------------


def _documento_vencido(db) -> DocumentoConhecimento:
    documento = db.scalar(
        select(DocumentoConhecimento).where(DocumentoConhecimento.situacao == "vencido")
    )
    assert documento is not None, "seed nao rodou: rode `make seed` antes dos testes"
    return documento


@pytest.mark.asyncio
async def test_fonte_vencida_nunca_e_recuperada(db, monkeypatch):
    """A fonte vencida esta indexada e seria o melhor resultado. Nao entra."""
    vencido = _documento_vencido(db)
    vetor_do_vencido = db.scalar(
        select(Chunk.vetor).where(Chunk.documento_id == vencido.id)
    )

    monkeypatch.setattr(
        conhecimento, "obter_provider", lambda: _ProviderFalso(list(vetor_do_vencido))
    )

    trechos = await buscar(db, "qualquer pergunta", limite=10)

    assert vencido.titulo not in {t["documento"] for t in trechos}


@pytest.mark.asyncio
async def test_fonte_vigente_com_o_mesmo_vetor_e_recuperada(db, monkeypatch):
    """Controle: a exclusao vem da vigencia, nao de um bug que zera a busca."""
    vigente = db.scalar(
        select(DocumentoConhecimento).where(DocumentoConhecimento.situacao == "vigente")
    )
    vetor = db.scalar(select(Chunk.vetor).where(Chunk.documento_id == vigente.id))

    monkeypatch.setattr(
        conhecimento, "obter_provider", lambda: _ProviderFalso(list(vetor))
    )

    trechos = await buscar(db, "qualquer pergunta", limite=10)

    assert vigente.titulo in {t["documento"] for t in trechos}
    assert trechos[0]["score"] == pytest.approx(1.0, abs=1e-3)


@pytest.mark.asyncio
async def test_trecho_distante_nao_vira_fonte(db, monkeypatch):
    """Um trecho semanticamente distante nao 'quase serve': ele nao sustenta."""
    dimensao = len(db.scalar(select(Chunk.vetor)))
    # Vetor ortogonal a tudo que foi indexado.
    monkeypatch.setattr(
        conhecimento, "obter_provider", lambda: _ProviderFalso([0.0] * (dimensao - 1) + [1.0])
    )

    trechos = await buscar(db, "assunto sem relacao alguma", limite=10)

    assert trechos == []
