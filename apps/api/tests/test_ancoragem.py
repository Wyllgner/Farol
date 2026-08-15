"""Testes da verificacao de ancoragem.

O que se prova aqui: uma afirmacao verificavel que nao consta na fonte
citada derruba a resposta. Numeros, prazos e enderecos sao o que a pessoa
vai executar — uma frase generica errada irrita, um prazo errado faz
alguem perder o curso.
"""

from app.services.ancoragem import verificar

FONTE = {
    "id": "c1",
    "texto": (
        "O certificado e liberado com frequencia minima de 75% e todas as "
        "atividades enviadas. O prazo de processamento e de 24 horas."
    ),
}
OUTRA_FONTE = {"id": "c2", "texto": "As inscricoes sao divulgadas por edital."}


def test_resposta_fiel_a_fonte_passa():
    a = verificar("A frequencia minima e de 75%.", [FONTE], ["c1"])
    assert a.intacta
    assert a.fontes_citadas == ["c1"]


def test_numero_inventado_bloqueia():
    """90% nao esta na fonte. A resposta e bloqueada, nao suavizada."""
    a = verificar("A frequencia minima e de 90%.", [FONTE], ["c1"])
    assert not a.intacta
    assert "90" in a.afirmacoes_sem_fonte


def test_prazo_inventado_bloqueia():
    a = verificar("O processamento leva 72 horas.", [FONTE], ["c1"])
    assert not a.intacta


def test_url_inventada_bloqueia():
    a = verificar("Acesse portal.exemplo.com para emitir.", [FONTE], ["c1"])
    assert not a.intacta


def test_resposta_sem_fonte_citada_bloqueia():
    """Uma resposta que nao aponta de onde veio nao carrega o carimbo."""
    a = verificar("A frequencia minima e de 75%.", [FONTE], [])
    assert not a.intacta
    assert "nenhuma fonte valida citada" in a.afirmacoes_sem_fonte


def test_fonte_citada_inexistente_bloqueia():
    a = verificar("A frequencia minima e de 75%.", [FONTE], ["c99"])
    assert not a.intacta


def test_lastro_e_so_a_fonte_citada():
    """Citar c2 nao autoriza afirmar o que so consta em c1."""
    a = verificar("A frequencia minima e de 75%.", [FONTE, OUTRA_FONTE], ["c2"])
    assert not a.intacta
    assert "75" in a.afirmacoes_sem_fonte


def test_resposta_vazia_bloqueia():
    assert not verificar("   ", [FONTE], ["c1"]).intacta


def test_texto_sem_afirmacao_verificavel_passa():
    """Sem numero, prazo ou endereco, nao ha o que conferir mecanicamente."""
    a = verificar("Verifique se todas as atividades foram enviadas.", [FONTE], ["c1"])
    assert a.intacta
