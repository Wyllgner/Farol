"""Testes do esclarecimento.

O que se prova aqui: "nao entendi" e reconhecido como incompreensao e nao
como pergunta nova, mas so quando a mensagem e SO isso. Uma frase que
carrega assunto ("nao entendi, e o prazo?") tem que ir para o pipeline,
senao o FAROL reescreve a resposta errada com muita clareza.
"""

from datetime import UTC, datetime, timedelta

import pytest

from app.db import SessionLocal
from app.enums import Canal, Categoria, DecisaoTriagem, SituacaoCaso
from app.models import Caso, Chunk, Conversa, DocumentoConhecimento
from app.services import esclarecimento


@pytest.fixture
def db():
    with SessionLocal() as sessao:
        yield sessao
        sessao.rollback()


@pytest.mark.parametrize(
    "texto",
    [
        "nao entendi",
        "Nao entendi.",
        "ainda nao entendi",
        "Ainda não entendi!",
        "nao ficou claro",
        "como assim?",
        "pode explicar melhor",
        "ficou confuso",
    ],
)
def test_reconhece_incompreensao(texto):
    assert esclarecimento.eh_incompreensao(texto)


@pytest.mark.parametrize(
    "texto",
    [
        "nao entendi, e o prazo da atividade 3?",
        "nao entendi como emitir o certificado",
        "como emito o certificado?",
        "obrigado",
        "",
    ],
)
def test_mensagem_com_assunto_vai_para_o_pipeline(texto):
    assert not esclarecimento.eh_incompreensao(texto)


def test_reescritas_contadas_pelo_log_comecam_em_zero(db):
    caso = Caso(
        canal=Canal.WHATSAPP,
        categoria=Categoria.SENHA,
        sensivel=False,
        confianca=0.8,
        decisao_triagem=DecisaoTriagem.RESPONDE,
        situacao=SituacaoCaso.RESPONDIDO,
        score_consequencia=1.0,
    )
    db.add(caso)
    db.flush()
    assert esclarecimento.reescritas_ja_feitas(db, caso) == 0


def test_trechos_do_caso_reconstituem_as_fontes_da_resposta(db):
    documento = DocumentoConhecimento(
        titulo="Redefinicao de senha (teste)",
        dono="Secretaria Academica",
        conteudo="Use o link Esqueci minha senha.",
        valido_ate=(datetime.now(UTC) + timedelta(days=30)).date(),
    )
    db.add(documento)
    db.flush()
    chunk = Chunk(documento_id=documento.id, ordem=0, texto="Use o link.")
    db.add(chunk)
    db.flush()

    caso = Caso(
        canal=Canal.WHATSAPP,
        categoria=Categoria.SENHA,
        sensivel=False,
        confianca=0.8,
        decisao_triagem=DecisaoTriagem.RESPONDE,
        situacao=SituacaoCaso.RESPONDIDO,
        score_consequencia=1.0,
        resposta_enviada="Use o link.",
        fontes_usadas=[{"chunk_id": str(chunk.id), "documento": documento.titulo}],
    )
    db.add(caso)
    db.flush()

    trechos = esclarecimento.trechos_do_caso(db, caso)
    assert [t["id"] for t in trechos] == [str(chunk.id)]
    assert trechos[0]["documento"] == documento.titulo


def test_sem_fontes_registradas_nao_ha_o_que_reescrever(db):
    caso = Caso(
        canal=Canal.WHATSAPP,
        categoria=Categoria.SENHA,
        sensivel=False,
        confianca=0.8,
        decisao_triagem=DecisaoTriagem.RESPONDE,
        situacao=SituacaoCaso.RESPONDIDO,
        score_consequencia=1.0,
        resposta_enviada="Use o link.",
    )
    db.add(caso)
    db.flush()
    assert esclarecimento.trechos_do_caso(db, caso) == []


def test_ultimo_caso_respondido_ignora_o_que_ja_escalou(db):
    conversa = Conversa(canal=Canal.WHATSAPP, handle_canal="+5569000000099")
    db.add(conversa)
    db.flush()

    escalado = Caso(
        conversa_id=conversa.id,
        canal=Canal.WHATSAPP,
        categoria=Categoria.SENHA,
        sensivel=False,
        confianca=0.0,
        decisao_triagem=DecisaoTriagem.ESCALA,
        situacao=SituacaoCaso.ESCALADO,
        score_consequencia=1.0,
        resposta_enviada="Texto qualquer.",
    )
    db.add(escalado)
    db.flush()

    assert esclarecimento.ultimo_caso_respondido(db, conversa.id) is None


@pytest.mark.parametrize("texto", ["bem?", "??", "e ai", "hein", "   ", "o que"])
def test_mensagem_curta_e_vaga(texto):
    assert esclarecimento.eh_vaga(texto)


@pytest.mark.parametrize(
    "texto",
    [
        "como faco para emitir o meu certificado",
        "o prazo da atividade 3 ja venceu ou nao",
        "nao consigo entrar na plataforma de jeito nenhum",
    ],
)
def test_pergunta_de_verdade_nao_e_vaga(texto):
    # Mensagem longa sem fonte continua escalando: ali existe pergunta, e
    # alguem precisa responde-la.
    assert not esclarecimento.eh_vaga(texto)


def test_pedido_de_reescrita_carrega_a_resposta_anterior():
    pedido = esclarecimento.pedido_de_reescrita("Use o link Esqueci minha senha.")
    assert "Esqueci minha senha" in pedido
    assert "NAO entendeu" in pedido
