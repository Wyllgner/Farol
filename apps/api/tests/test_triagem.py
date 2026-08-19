"""Testes da Politica de Triagem.

Codigo puro, sem banco e sem rede: a decisao de escalar e deterministica
por design, e um teste que precisasse de modelo para verifica-la ja seria
a prova de que o design falhou.
"""

import pytest

from app.enums import Categoria, DecisaoTriagem
from app.services.triagem import (
    CONFIANCA_ALTA,
    CONFIANCA_MEDIA,
    calcular_confianca,
    decidir,
)


def test_confianca_alta_responde_direto():
    d = decidir(Categoria.CERTIFICADO, 0.90, tem_fonte=True, nao_sei=False)
    assert d.decisao is DecisaoTriagem.RESPONDE
    assert not d.escala


def test_confianca_media_oferece_humano():
    d = decidir(Categoria.CERTIFICADO, 0.55, tem_fonte=True, nao_sei=False)
    assert d.decisao is DecisaoTriagem.RESPONDE_COM_OFERTA_HUMANA
    assert not d.escala


def test_confianca_baixa_escala():
    d = decidir(Categoria.CERTIFICADO, 0.20, tem_fonte=True, nao_sei=False)
    assert d.escala


def test_sem_fonte_escala_mesmo_com_confianca_alta():
    d = decidir(Categoria.PRAZO, 0.99, tem_fonte=False, nao_sei=False)
    assert d.escala
    assert "sem fonte" in d.motivo


def test_nao_sei_escala():
    d = decidir(Categoria.ACESSO, 0.99, tem_fonte=True, nao_sei=True)
    assert d.escala


@pytest.mark.parametrize("categoria", [Categoria.SENSIVEL, Categoria.RECLAMACAO])
def test_categoria_sensivel_escala_sempre(categoria):
    """Independentemente da confianca, inclusive com confianca maxima.

    Uma resposta muito confiante sobre dado pessoal e exatamente o caso
    que nao pode passar.
    """
    d = decidir(categoria, 1.0, tem_fonte=True, nao_sei=False)
    assert d.escala
    assert d.sensivel


def test_sensibilidade_avaliada_antes_da_confianca():
    """A ordem da tabela importa: sensivel vence qualquer outro criterio."""
    for confianca in (0.0, CONFIANCA_MEDIA, CONFIANCA_ALTA, 1.0):
        assert decidir(Categoria.SENSIVEL, confianca, True, False).escala


# --------------------------------------------------------------------------
# Score de confianca
# --------------------------------------------------------------------------


def test_ancoragem_rompida_zera_a_confianca():
    """Nao reduz um pouco: zera. A resposta ja foi bloqueada."""
    assert calcular_confianca(1.0, 1.0, ancoragem_intacta=False, degradado=False) == 0.0


def test_degradado_rebaixa_a_propria_confianca():
    normal = calcular_confianca(0.8, 0.8, True, degradado=False)
    degradado = calcular_confianca(0.8, 0.8, True, degradado=True)
    assert degradado < normal


def test_fonte_pesa_mais_que_classificacao():
    """Errar a categoria costuma ser recuperavel; responder sem base nao."""
    fonte_boa = calcular_confianca(0.2, 0.9, True, False)
    classificacao_boa = calcular_confianca(0.9, 0.2, True, False)
    assert fonte_boa > classificacao_boa


def test_confianca_permanece_no_intervalo():
    assert 0.0 <= calcular_confianca(1.0, 1.0, True, False) <= 1.0
    assert 0.0 <= calcular_confianca(0.0, 0.0, True, True) <= 1.0
