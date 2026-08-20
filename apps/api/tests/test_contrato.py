"""Testes do Contrato de Resolucao e da fila.

O laco so vale se a regra central for inviolavel: no "nao resolveu", o
sistema NAO repete a resposta. Ele escala, avisando que a orientacao
padrao ja falhou.
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.db import SessionLocal
from app.enums import (
    Canal,
    Categoria,
    ContratoResolucao,
    DecisaoTriagem,
    SituacaoCaso,
)
from app.models import Caso, DocumentoConhecimento
from app.services import contrato, fila


@pytest.fixture
def db():
    with SessionLocal() as sessao:
        yield sessao
        sessao.rollback()


def _caso_respondido(db, categoria=Categoria.CERTIFICADO, idade=timedelta(hours=3)):
    caso = Caso(
        canal=Canal.WHATSAPP,
        categoria=categoria,
        sensivel=False,
        confianca=0.8,
        decisao_triagem=DecisaoTriagem.RESPONDE,
        situacao=SituacaoCaso.RESPONDIDO,
        score_consequencia=2.5,
    )
    db.add(caso)
    db.flush()
    caso.criado_em = datetime.now(UTC) - idade
    db.flush()
    return caso


# --------------------------------------------------------------------------
# Abertura e pergunta
# --------------------------------------------------------------------------


def test_caso_respondido_nasce_com_contrato_aberto(db):
    caso = _caso_respondido(db)
    contrato.abrir(caso, "Emita pela pagina do curso.", [
        {"id": "c1", "documento": "Emissao do certificado"}
    ])
    assert caso.contrato_resolucao is ContratoResolucao.ABERTO
    assert caso.resposta_enviada
    assert caso.fontes_usadas[0]["documento"] == "Emissao do certificado"


def test_so_pergunta_depois_da_espera(db):
    recente = _caso_respondido(db, idade=timedelta(minutes=5))
    contrato.abrir(recente, "resposta", [])
    db.flush()

    pendentes = contrato.pendentes_de_pergunta(db)
    assert recente.id not in {c.id for c in pendentes}, (
        "perguntar cedo demais interrompe quem ainda esta executando"
    )


def test_pergunta_usa_o_vocabulario_do_caso(db):
    assert "certificado" in contrato.pergunta_de("certificado")
    assert "dois fatores" in contrato.pergunta_de("2fa")
    # Categoria sem pergunta especifica ainda recebe algo concreto.
    assert contrato.pergunta_de("outros").endswith("?")


def test_pergunta_sai_uma_vez_so(db):
    caso = _caso_respondido(db)
    contrato.abrir(caso, "resposta", [])
    db.flush()

    contrato.marcar_perguntado(db, caso)
    pendentes = contrato.pendentes_de_pergunta(db)

    assert caso.id not in {c.id for c in pendentes}, (
        "perguntar duas vezes seria a interrupcao que o produto quer evitar"
    )


# --------------------------------------------------------------------------
# Confirmacao e falha
# --------------------------------------------------------------------------


def test_sim_encerra_o_caso(db):
    caso = _caso_respondido(db)
    contrato.abrir(caso, "resposta", [])
    contrato.marcar_perguntado(db, caso)

    contrato.confirmar(db, caso)

    assert caso.contrato_resolucao is ContratoResolucao.CONFIRMADO
    assert caso.situacao is SituacaoCaso.ENCERRADO
    assert caso.encerrado_em is not None


def test_nao_escala_e_registra_que_a_orientacao_falhou(db):
    """A regra central do laco."""
    caso = _caso_respondido(db)
    contrato.abrir(caso, "A frequencia minima e de 75%.", [
        {"id": "c1", "documento": "Emissao do certificado"}
    ])
    contrato.marcar_perguntado(db, caso)

    contrato.registrar_falha(db, caso)

    assert caso.contrato_resolucao is ContratoResolucao.FALHOU
    assert caso.situacao is SituacaoCaso.ESCALADO
    assert caso.orientacao_padrao_falhou is True
    # O servidor precisa ver o que ja foi tentado antes de escrever.
    assert caso.dossie["resposta_que_falhou"] == "A frequencia minima e de 75%."
    assert "NAO resolveu" in caso.dossie["resumo"]


def test_falha_rebaixa_a_fonte_e_confirmacao_promove(db):
    documento = db.scalar(
        select(DocumentoConhecimento).where(
            DocumentoConhecimento.titulo == "Emissao do certificado"
        )
    )
    documento.taxa_resolucao = 50
    db.flush()
    fontes = [{"id": "c1", "documento": documento.titulo}]

    ruim = _caso_respondido(db)
    contrato.abrir(ruim, "resposta", fontes)
    contrato.registrar_falha(db, ruim)
    apos_falha = float(documento.taxa_resolucao)

    bom = _caso_respondido(db)
    contrato.abrir(bom, "resposta", fontes)
    contrato.confirmar(db, bom)

    assert apos_falha < 50, "fonte que falhou tem de perder peso"
    assert float(documento.taxa_resolucao) > apos_falha


def test_sem_retorno_vai_para_baixa_prioridade(db):
    caso = _caso_respondido(db)
    contrato.abrir(caso, "resposta", [])
    contrato.marcar_perguntado(db, caso)
    caso.contrato_perguntado_em = datetime.now(UTC) - timedelta(days=5)
    db.flush()

    contrato.expirar_sem_retorno(db)

    assert caso.contrato_resolucao is ContratoResolucao.SEM_RETORNO
    assert float(caso.score_consequencia) == 0
    assert caso.situacao is SituacaoCaso.RESPONDIDO, "silencio nao e confirmacao"


# --------------------------------------------------------------------------
# Fila
# --------------------------------------------------------------------------


def test_fila_ordena_por_consequencia_e_nao_por_chegada(db):
    antigo_barato = _caso_respondido(db, idade=timedelta(days=2))
    antigo_barato.situacao = SituacaoCaso.ESCALADO
    antigo_barato.score_consequencia = 1

    novo_caro = _caso_respondido(db, idade=timedelta(minutes=1))
    novo_caro.situacao = SituacaoCaso.ESCALADO
    novo_caro.score_consequencia = 9
    db.flush()

    ordem = [c.id for c in fila.listar(db)]
    assert ordem.index(novo_caro.id) < ordem.index(antigo_barato.id)


def test_duplicado_nao_aparece_na_fila(db):
    original = _caso_respondido(db)
    original.situacao = SituacaoCaso.ESCALADO
    duplicado = _caso_respondido(db)
    duplicado.situacao = SituacaoCaso.ESCALADO
    db.flush()

    fila.marcar_duplicado(db, duplicado, original)

    ids = {c.id for c in fila.listar(db)}
    assert duplicado.id not in ids
    assert original.id in ids


def test_contato_repetido_aumenta_a_prioridade_do_original(db):
    original = _caso_respondido(db)
    original.situacao = SituacaoCaso.ESCALADO
    original.score_consequencia = 3
    duplicado = _caso_respondido(db)
    db.flush()

    fila.marcar_duplicado(db, duplicado, original)

    assert float(original.score_consequencia) == 4, (
        "procurar duas vezes e sinal de urgencia real"
    )


def test_responder_registra_se_o_rascunho_foi_editado(db):
    from app.models import LogAuditoria

    caso = _caso_respondido(db)
    caso.situacao = SituacaoCaso.ESCALADO
    caso.rascunho_resposta = "rascunho original"
    db.flush()

    fila.responder(db, caso, "texto reescrito pelo servidor", "Servidora Ana")

    assert caso.situacao is SituacaoCaso.ENCERRADO
    log = db.scalars(
        select(LogAuditoria).where(LogAuditoria.caso_id == caso.id)
    ).all()
    assert any(
        entrada.etapa == "resposta_humana" and entrada.payload["editou_o_rascunho"]
        for entrada in log
    )


async def test_aprovar_conhecimento_nasce_com_validade(db, monkeypatch):
    from app.services import conhecimento

    class ProviderFalso:
        nome = "teste"

        async def embutir(self, textos):
            dimensao = len(db.scalar(select(__import__("app.models", fromlist=["Chunk"]).Chunk.vetor)))
            return [[0.0] * dimensao for _ in textos]

    monkeypatch.setattr(conhecimento, "provider_ativo", lambda: ProviderFalso())

    caso = _caso_respondido(db)
    caso.resposta_enviada = "Procedimento novo confirmado pela Secretaria."
    db.flush()

    documento = await fila.aprovar_como_conhecimento(
        db, caso, "Procedimento novo", "Servidora Ana"
    )

    assert documento.aprovado_por_servidor
    assert documento.valido_ate is not None, (
        "conhecimento sem prazo e o proximo documento vencido respondendo"
    )
    assert documento.chunks, "precisa ficar citavel imediatamente"
