"""Testes da continuidade da conversa.

O que se prova aqui: uma pergunta que depende do turno anterior e
reconhecida pela FORMA (pronome sem referente, conector inicial,
brevidade), sem que o modulo precise entender o assunto. E que a consulta
de recuperacao soma os dois turnos em vez de substituir um pelo outro,
porque a mensagem nova pode estar trocando de assunto.
"""

import pytest

from app.services.seguimento import (
    bloco_de_contexto,
    consulta_com_contexto,
    eh_seguimento,
    ultima_pergunta,
)


@pytest.mark.parametrize(
    "texto",
    [
        "mas que curso e esse?",
        "e o prazo?",
        "entao como faco",
        "esse mesmo",
        "e ele ja venceu?",
        "qual o prazo",
        "onde vejo isso",
    ],
)
def test_pergunta_presa_no_turno_anterior(texto):
    assert eh_seguimento(texto)


@pytest.mark.parametrize(
    "texto",
    [
        "como faco para emitir o meu certificado do curso",
        "nao consigo entrar na plataforma com a minha senha",
        "quando comecam as inscricoes para o proximo curso de mediacao",
    ],
)
def test_pergunta_que_se_sustenta_sozinha(texto):
    assert not eh_seguimento(texto)


def test_consulta_soma_os_dois_turnos():
    consulta = consulta_com_contexto("mas que curso e esse?", "qual o prazo da aula")
    # Somar, e nao substituir: o termo novo tem que competir na busca em
    # pe de igualdade com o assunto anterior.
    assert "prazo da aula" in consulta
    assert "que curso e esse" in consulta


def test_sem_turno_anterior_a_consulta_e_a_propria_pergunta():
    assert consulta_com_contexto("e o prazo?", "") == "e o prazo?"
    assert bloco_de_contexto([]) == ""


def test_contexto_avisa_que_nao_e_fonte():
    bloco = bloco_de_contexto(
        [("entrada", "qual o prazo"), ("saida", "O prazo encerra as 23h59.")]
    )
    # A ancoragem nao ganha excecao por causa do historico: o que pode
    # sustentar afirmacao continua sendo so o trecho oficial. A resposta
    # anterior do FAROL esta neste bloco, e ela contem prazos: se valesse
    # como fonte, um numero errado viraria verdade por citacao circular.
    assert "NAO e fonte" in bloco
    assert "23h59" in bloco


def test_contexto_traz_a_sessao_inteira_na_ordem():
    bloco = bloco_de_contexto(
        [
            ("entrada", "qual o prazo da aula"),
            ("saida", "Faltam 3 dias."),
            ("entrada", "e o certificado"),
            ("saida", "Precisa de 75% de frequencia."),
        ]
    )
    assert bloco.index("qual o prazo da aula") < bloco.index("e o certificado")
    assert "Pessoa:" in bloco and "FAROL:" in bloco


def test_ultima_pergunta_ignora_o_que_o_farol_disse():
    historico = [
        ("entrada", "qual o prazo da aula"),
        ("saida", "Faltam 3 dias."),
    ]
    assert ultima_pergunta(historico) == "qual o prazo da aula"
    assert ultima_pergunta([]) == ""
