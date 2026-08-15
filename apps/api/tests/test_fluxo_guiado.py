"""Testes do fluxo guiado de 2FA.

O caminho feliz importa menos que o caminho de falha: acompanhar so vale
a pena se o sistema souber a hora de parar de insistir.
"""

import pytest
from sqlalchemy import select

from app.db import SessionLocal
from app.enums import Canal, Categoria, Direcao, SituacaoCaso
from app.models import Caso, Conversa, Mensagem
from app.services import fluxo_guiado
from app.services.conversa import _continuar_fluxo, _iniciar_fluxo, obter_ou_criar
from app.services.fluxo_guiado import (
    LIMITE_FALHAS,
    NAO,
    SIM,
    Estado,
    avancar,
    deve_oferecer,
    iniciar,
)


@pytest.fixture
def db():
    with SessionLocal() as sessao:
        yield sessao
        sessao.rollback()


# --------------------------------------------------------------------------
# Maquina de estados, isolada
# --------------------------------------------------------------------------


def test_inicia_no_primeiro_passo_com_progresso_visivel():
    p = iniciar("2fa")
    assert "Passo 1 de 5" in p.texto
    assert p.estado.passo == 0
    assert SIM in p.acoes_rapidas and NAO in p.acoes_rapidas


def test_cada_passo_tem_verificacao():
    """A pergunta de verificacao e o que separa acompanhar de orientar."""
    for passo in fluxo_guiado.FLUXO_2FA.passos:
        assert passo.verificacao.endswith("?")
        assert passo.alternativa, "todo passo precisa de caminho alternativo"


def test_sucesso_avanca_e_mostra_progresso():
    estado = Estado(fluxo="2fa", passo=0)
    p = avancar(estado, SIM)
    assert p.estado.passo == 1
    assert "Passo 2 de 5" in p.texto


def test_falha_oferece_alternativa_e_nao_repete_a_instrucao():
    """Repetir a mesma instrucao seria o banner de novo, so que mais lento."""
    estado = Estado(fluxo="2fa", passo=0)
    original = fluxo_guiado.FLUXO_2FA.passos[0]

    p = avancar(estado, NAO)

    assert p.estado.passo == 0, "nao avanca enquanto nao destravar"
    assert p.estado.falhas_consecutivas == 1
    assert original.alternativa in p.texto
    assert original.instrucao not in p.texto


def test_duas_falhas_consecutivas_escalam():
    estado = Estado(fluxo="2fa", passo=1, falhas_consecutivas=LIMITE_FALHAS - 1)
    p = avancar(estado, NAO)

    assert p.escalar
    assert p.estado is None, "fluxo encerrado ao escalar"
    assert p.acoes_rapidas == [], "ninguem fica preso tentando de novo"


def test_acerto_zera_o_contador_de_falhas():
    """Duas falhas SEGUIDAS e o sinal, nao duas ao longo do fluxo inteiro."""
    estado = Estado(fluxo="2fa", passo=0, falhas_consecutivas=1)
    p = avancar(estado, SIM)
    assert p.estado.falhas_consecutivas == 0


def test_ultimo_passo_conclui():
    ultimo = fluxo_guiado.FLUXO_2FA.total - 1
    p = avancar(Estado(fluxo="2fa", passo=ultimo), SIM)
    assert p.concluido
    assert p.estado is None


def test_percurso_completo_sem_falhas():
    p = iniciar("2fa")
    for _ in range(fluxo_guiado.FLUXO_2FA.total):
        assert not p.escalar
        p = avancar(p.estado, SIM)
    assert p.concluido


# --------------------------------------------------------------------------
# Quando oferecer
# --------------------------------------------------------------------------


def test_oferece_a_quem_nao_tem_2fa():
    estado = {"cursos": [{"dois_fatores_configurado": False}]}
    assert deve_oferecer(Categoria.DOIS_FATORES, estado) == "2fa"


def test_nao_oferece_a_quem_ja_configurou():
    """Propor a quem ja tem seria ruido."""
    estado = {"cursos": [{"dois_fatores_configurado": True}]}
    assert deve_oferecer(Categoria.DOIS_FATORES, estado) is None


def test_oferece_a_anonimo():
    """O procedimento e publico e nao revela nada."""
    assert deve_oferecer(Categoria.DOIS_FATORES, {}) == "2fa"


def test_nao_oferece_para_outra_categoria():
    assert deve_oferecer(Categoria.CERTIFICADO, {}) is None


# --------------------------------------------------------------------------
# Persistencia e escalonamento com dossie
# --------------------------------------------------------------------------


def test_estado_do_fluxo_persiste_na_conversa(db):
    conversa = obter_ou_criar(db, Canal.WHATSAPP, "+5569900000999")
    _iniciar_fluxo(db, conversa, "2fa")

    recarregada = db.scalar(select(Conversa).where(Conversa.id == conversa.id))
    assert recarregada.fluxo_estado["fluxo"] == "2fa"
    assert recarregada.fluxo_estado["passo"] == 0


def test_escalonamento_registra_o_passo_em_que_travou(db):
    """A informacao mais valiosa: onde exatamente a orientacao falhou."""
    conversa = obter_ou_criar(db, Canal.WHATSAPP, "+5569900000998")
    estado = Estado(fluxo="2fa", passo=2, falhas_consecutivas=LIMITE_FALHAS - 1)

    _continuar_fluxo(db, conversa, estado, NAO)

    caso = db.scalar(
        select(Caso)
        .where(Caso.conversa_id == conversa.id)
        .where(Caso.situacao == SituacaoCaso.ESCALADO)
    )
    assert caso is not None
    assert caso.orientacao_padrao_falhou is True
    assert caso.dossie["passo_em_que_travou"]["indice"] == 3
    assert caso.dossie["passo_em_que_travou"]["chave"] == "aplicativo"
    assert caso.dossie["passo_em_que_travou"]["alternativa_ja_tentada"]
    assert conversa.fluxo_estado is None, "fluxo encerrado apos escalar"


def test_dialogo_fica_registrado(db):
    from app.services.conversa import registrar_mensagem

    conversa = obter_ou_criar(db, Canal.WHATSAPP, "+5569900000997")
    registrar_mensagem(db, conversa, Direcao.ENTRADA, "nao consigo o 2fa")
    registrar_mensagem(db, conversa, Direcao.SAIDA, "vamos juntos", [SIM, NAO])

    mensagens = db.scalars(
        select(Mensagem).where(Mensagem.conversa_id == conversa.id)
    ).all()
    assert len(mensagens) == 2
    assert {m.direcao for m in mensagens} == {Direcao.ENTRADA, Direcao.SAIDA}
