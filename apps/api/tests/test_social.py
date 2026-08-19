"""Testes da conversa social.

O que se prova aqui: cortesia e reconhecida e respondida sem escalar, e
uma pergunta real nunca e confundida com cortesia, mesmo quando comeca
com uma saudacao. O segundo caso e o que importa: errar para o lado de
"isto e um oi" faria o FAROL responder "ola" a quem perdeu o prazo.
"""

import pytest

from app.services.social import Intencao, detectar, responder


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("oi", Intencao.SAUDACAO),
        ("Oi!!", Intencao.SAUDACAO),
        ("olá", Intencao.SAUDACAO),
        ("bom dia", Intencao.SAUDACAO),
        ("Boa tarde!", Intencao.SAUDACAO),
        ("oi, tudo bem?", Intencao.SAUDACAO),
        ("e ai, blz?", Intencao.SAUDACAO),
        ("obrigado", Intencao.AGRADECIMENTO),
        ("obrigada mesmo!", Intencao.AGRADECIMENTO),
        ("vlw", Intencao.AGRADECIMENTO),
        ("tchau", Intencao.DESPEDIDA),
        ("ate mais", Intencao.DESPEDIDA),
        ("ok", Intencao.RECONHECIMENTO),
        ("entendi", Intencao.RECONHECIMENTO),
        ("quem e voce?", Intencao.APRESENTACAO),
        ("o que voce faz", Intencao.APRESENTACAO),
        ("pode me ajudar?", Intencao.APRESENTACAO),
    ],
)
def test_reconhece_conversa_social(texto, esperado):
    assert detectar(texto) is esperado


@pytest.mark.parametrize(
    "texto",
    [
        "como emito meu certificado?",
        "bom dia, meu certificado nao sai",
        "oi, esqueci minha senha",
        "obrigado, mas o prazo ja passou?",
        "ok e o link da webconferencia?",
        "tudo bem com o prazo da atividade 3?",
        "",
        "   ",
    ],
)
def test_pergunta_real_nunca_vira_saudacao(texto):
    assert detectar(texto) is None


def test_agradecimento_tem_prioridade_sobre_despedida():
    assert detectar("obrigado, ate mais") is Intencao.AGRADECIMENTO


def test_resposta_usa_o_primeiro_nome_quando_ha_identidade():
    assert "Ana" in responder(Intencao.SAUDACAO, "Ana")


def test_resposta_anonima_nao_deixa_lacuna_no_texto():
    texto = responder(Intencao.SAUDACAO)
    assert "{" not in texto
    assert " ," not in texto
