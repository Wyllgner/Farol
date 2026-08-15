"""Testes do pipeline de resolucao, de ponta a ponta.

Sao os tres casos que definem se o motor faz o que promete:
  1. responde ancorado em fonte oficial
  2. recusa e escala quando nao ha fonte
  3. escala categoria sensivel mesmo com confianca alta

Rodam sem rede: um provider falso substitui o modelo, e o vetor da
pergunta vem de um trecho ja indexado. O que se testa aqui e a logica do
motor, nao a qualidade do modelo.
"""

import pytest
from sqlalchemy import select

from app.db import SessionLocal
from app.enums import Canal, Categoria, DecisaoTriagem, NivelIdentidade, SituacaoCaso
from app.llm.base import Classificacao, RespostaAncorada
from app.models import Chunk, DocumentoConhecimento, LogAuditoria, Participante
from app.services import atendimento as servico
from app.services import conhecimento
from app.services.atendimento import atender


class ProviderFalso:
    """Modelo controlado: devolve exatamente o que o teste precisa."""

    nome = "openai"

    def __init__(self, categoria, texto="", fontes=None, nao_sei=False, vetor=None):
        self._categoria = categoria
        self._texto = texto
        self._fontes = fontes or []
        self._nao_sei = nao_sei
        self._vetor = vetor

    async def classificar(self, texto):
        return Classificacao(categoria=self._categoria, confianca=0.9)

    async def gerar_ancorado(self, pergunta, trechos):
        fontes = self._fontes
        if fontes == ["__primeiro__"]:
            fontes = [trechos[0]["id"]] if trechos else []
        return RespostaAncorada(
            texto=self._texto, fontes=fontes, nao_sei=self._nao_sei
        )

    async def embutir(self, textos):
        return [self._vetor for _ in textos]


@pytest.fixture
def db():
    with SessionLocal() as sessao:
        yield sessao
        sessao.rollback()


@pytest.fixture
def sem_ensaio(monkeypatch):
    """Desliga o Modo Ensaio para testar o caminho de resposta direta.

    Com o ensaio ligado nada e enviado automaticamente — que e o correto,
    mas nao e o que estes testes verificam.
    """
    from app.config import settings

    monkeypatch.setattr(settings, "modo_ensaio", False)


@pytest.fixture
def doc_certificado(db):
    """Documento vigente sobre certificado, com seu vetor e trecho."""
    documento = db.scalar(
        select(DocumentoConhecimento).where(
            DocumentoConhecimento.titulo == "Emissao do certificado"
        )
    )
    assert documento is not None, "rode `make seed` antes dos testes"
    chunk = db.scalar(select(Chunk).where(Chunk.documento_id == documento.id))
    return documento, chunk


def _instalar(monkeypatch, provider):
    """O provider falso precisa valer tambem dentro da recuperacao."""
    monkeypatch.setattr(servico, "obter_provider", lambda: provider)
    monkeypatch.setattr(conhecimento, "obter_provider", lambda: provider)


# --------------------------------------------------------------------------
# Caso 1 — responde ancorado
# --------------------------------------------------------------------------


async def test_responde_ancorado_em_fonte_oficial(
    db, monkeypatch, doc_certificado, sem_ensaio
):
    _, chunk = doc_certificado
    _instalar(
        monkeypatch,
        ProviderFalso(
            categoria=Categoria.CERTIFICADO,
            # Afirmacao que consta literalmente na fonte.
            texto="O certificado exige frequencia minima de 75%.",
            fontes=["__primeiro__"],
            vetor=list(chunk.vetor),
        ),
    )

    r = await atender(db, canal=Canal.WHATSAPP, handle="", pergunta="como emito o certificado")

    assert not r.escalou
    assert r.decisao.decisao in (
        DecisaoTriagem.RESPONDE,
        DecisaoTriagem.RESPONDE_COM_OFERTA_HUMANA,
    )
    assert r.ancoragem.intacta
    assert r.trechos, "resposta sem fonte nao deveria ter passado"
    assert r.caso.situacao is SituacaoCaso.RESPONDIDO


# --------------------------------------------------------------------------
# Caso 2 — recusa e escala sem fonte
# --------------------------------------------------------------------------


async def test_recusa_e_escala_quando_nao_ha_fonte(db, monkeypatch):
    dimensao = len(db.scalar(select(Chunk.vetor)))
    _instalar(
        monkeypatch,
        ProviderFalso(
            categoria=Categoria.OUTROS,
            nao_sei=True,
            # Vetor ortogonal: nada na base sustenta a pergunta.
            vetor=[0.0] * (dimensao - 1) + [1.0],
        ),
    )

    r = await atender(
        db, canal=Canal.WHATSAPP, handle="", pergunta="qual o valor do auxilio-moradia"
    )

    assert r.escalou
    assert r.trechos == []
    assert r.caso.situacao is SituacaoCaso.ESCALADO
    assert r.caso.dossie is not None
    assert "encaminhei seu caso" in r.resposta


async def test_afirmacao_sem_fonte_e_bloqueada(db, monkeypatch, doc_certificado):
    """Confianca alta e fonte recuperada, mas o modelo inventou um numero."""
    _, chunk = doc_certificado
    _instalar(
        monkeypatch,
        ProviderFalso(
            categoria=Categoria.CERTIFICADO,
            texto="O certificado exige frequencia minima de 42%.",  # nao consta
            fontes=["__primeiro__"],
            vetor=list(chunk.vetor),
        ),
    )

    r = await atender(db, canal=Canal.WHATSAPP, handle="", pergunta="qual a frequencia minima")

    assert not r.ancoragem.intacta
    assert r.escalou, "afirmacao sem fonte tem de ser bloqueada, nao suavizada"
    assert r.decisao.confianca == 0.0


# --------------------------------------------------------------------------
# Caso 3 — categoria sensivel escala sempre
# --------------------------------------------------------------------------


async def test_categoria_sensivel_escala_com_confianca_alta(db, monkeypatch, doc_certificado):
    _, chunk = doc_certificado
    _instalar(
        monkeypatch,
        ProviderFalso(
            categoria=Categoria.SENSIVEL,
            texto="Resposta que jamais deveria sair.",
            fontes=["__primeiro__"],
            vetor=list(chunk.vetor),
        ),
    )

    r = await atender(
        db, canal=Canal.WHATSAPP, handle="", pergunta="preciso do meu cpf cadastrado"
    )

    assert r.escalou
    assert r.caso.sensivel
    assert "Resposta que jamais deveria sair" not in r.resposta


# --------------------------------------------------------------------------
# Identidade progressiva e auditoria
# --------------------------------------------------------------------------


async def test_anonimo_nao_recebe_dado_pessoal(
    db, monkeypatch, doc_certificado, sem_ensaio
):
    _, chunk = doc_certificado
    _instalar(
        monkeypatch,
        ProviderFalso(
            categoria=Categoria.CERTIFICADO,
            texto="Emita pela pagina do curso.",
            fontes=["__primeiro__"],
            vetor=list(chunk.vetor),
        ),
    )

    r = await atender(db, canal=Canal.WHATSAPP, handle="", pergunta="e meu certificado")

    assert r.identidade.nivel is NivelIdentidade.ANONIMO
    assert r.identidade.participante is None


async def test_contato_conhecido_e_reconhecido(
    db, monkeypatch, doc_certificado, sem_ensaio
):
    _, chunk = doc_certificado
    participante = db.scalar(select(Participante).where(Participante.telefone.is_not(None)))
    _instalar(
        monkeypatch,
        ProviderFalso(
            categoria=Categoria.CERTIFICADO,
            texto="Emita pela pagina do curso.",
            fontes=["__primeiro__"],
            vetor=list(chunk.vetor),
        ),
    )

    r = await atender(
        db, canal=Canal.WHATSAPP, handle=participante.telefone, pergunta="e meu certificado"
    )

    assert r.identidade.nivel is NivelIdentidade.RECONHECIDO
    # Reconhecido nao concede acesso a dado sensivel.
    assert not r.identidade.pode_ver_sensivel()


async def test_toda_interacao_deixa_rastro(db, monkeypatch, doc_certificado):
    _, chunk = doc_certificado
    antes = db.scalar(select(LogAuditoria.id).limit(1)) is not None
    _instalar(
        monkeypatch,
        ProviderFalso(
            categoria=Categoria.CERTIFICADO,
            texto="Emita pela pagina do curso.",
            fontes=["__primeiro__"],
            vetor=list(chunk.vetor),
        ),
    )

    await atender(db, canal=Canal.WHATSAPP, handle="", pergunta="certificado")

    etapas = set(db.scalars(select(LogAuditoria.etapa)).all())
    assert {"entrada", "classificacao", "recuperacao", "ancoragem", "triagem"} <= etapas
    assert antes or etapas


# --------------------------------------------------------------------------
# Modo Ensaio
# --------------------------------------------------------------------------


async def test_modo_ensaio_gera_mas_nao_envia(db, monkeypatch, doc_certificado):
    """A resposta existe e vai para revisao; o participante nao a recebe."""
    from app.config import settings
    from app.services import ensaio

    monkeypatch.setattr(settings, "modo_ensaio", True)
    _, chunk = doc_certificado
    _instalar(
        monkeypatch,
        ProviderFalso(
            categoria=Categoria.CERTIFICADO,
            texto="O certificado exige frequencia minima de 75%.",
            fontes=["__primeiro__"],
            vetor=list(chunk.vetor),
        ),
    )

    r = await atender(db, canal=Canal.WHATSAPP, handle="", pergunta="como emito")

    assert r.retido
    assert not r.foi_entregue
    assert r.caso.em_ensaio
    assert r.caso.situacao is SituacaoCaso.ESCALADO
    # A resposta gerada fica guardada para o servidor conferir...
    assert "75%" in r.caso.rascunho_resposta
    # ...e nao e o que o participante recebe.
    assert "75%" not in r.resposta
    assert r.resposta == ensaio.AVISO_AO_PARTICIPANTE


async def test_categoria_liberada_volta_a_responder(db, monkeypatch, doc_certificado):
    from app.config import settings
    from app.services import ensaio

    monkeypatch.setattr(settings, "modo_ensaio", True)
    ensaio.liberar(db, Categoria.CERTIFICADO, "Servidora Ana")

    _, chunk = doc_certificado
    _instalar(
        monkeypatch,
        ProviderFalso(
            categoria=Categoria.CERTIFICADO,
            texto="O certificado exige frequencia minima de 75%.",
            fontes=["__primeiro__"],
            vetor=list(chunk.vetor),
        ),
    )

    r = await atender(db, canal=Canal.WHATSAPP, handle="", pergunta="como emito")

    assert not r.retido
    assert r.foi_entregue
    assert "75%" in r.resposta
