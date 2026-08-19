"""Testes do Andar 1: antecipacao, orcamento e verificacao de efeito.

O que precisa ficar provado: a mensagem proativa nasce com hipotese, a
hipotese e conferida no prazo, e o gatilho que nao funciona sai do ar
sozinho. Sem isso o FAROL seria apenas um banner mais sofisticado.
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.db import SessionLocal
from app.enums import (
    Canal,
    Categoria,
    DecisaoTriagem,
    EfeitoAntecipacao,
    SituacaoCaso,
    SituacaoCertificado,
)
from app.models import Caso, EventoProativo, Matricula, Participante
from app.services import antecipacao, atencao, entrega, gatilhos


@pytest.fixture
def db():
    with SessionLocal() as sessao:
        yield sessao
        sessao.rollback()


@pytest.fixture
def regras():
    return gatilhos.carregar()


@pytest.fixture
def disponivel(db) -> Participante:
    """Participante que aceita avisos, tem saldo e nenhuma hipotese aberta.

    O seed inclui gente que ja optou por nao receber: pegar "o primeiro"
    tornaria o teste dependente da ordem do banco.

    A ausencia de evento proativo tambem e requisito, e nao detalhe. Estes
    testes exercitam a PRIMEIRA interrupcao de alguem, e o motor barra um
    gatilho que ja disparou para a mesma pessoa. Rodar a demonstracao ou
    semear o historico enche o banco de eventos; sem este filtro o teste
    passava ou falhava conforme o que tivesse sido executado antes dele,
    que e a pior especie de teste: o que mente nas duas direcoes.
    """
    com_evento = select(EventoProativo.participante_id)
    participante = db.scalars(
        select(Participante)
        .where(Participante.aceita_avisos.is_(True))
        .where(Participante.saldo_atencao > 0)
        .where(Participante.id.not_in(com_evento))
        .order_by(Participante.email)
    ).first()
    assert participante is not None, (
        "nenhum participante sem hipotese aberta: rode `make seed` "
        "(ou `python -m app.seed`) antes dos testes"
    )
    return participante


def _matricula_de(db, **filtros) -> Matricula:
    consulta = select(Matricula)
    for campo, valor in filtros.items():
        consulta = consulta.where(getattr(Matricula, campo) == valor)
    matricula = db.scalars(consulta).first()
    assert matricula is not None, "rode `make seed` antes dos testes"
    return matricula


# --------------------------------------------------------------------------
# Regras declarativas
# --------------------------------------------------------------------------

def _hipotese_entregue(db, participante, gatilho, agora):
    """Hipotese de uma mensagem que CHEGOU a pessoa.

    Registrar a hipotese e entregar a mensagem viraram dois momentos
    distintos: so o segundo comeca o relogio da verificacao. Os testes que
    medem efetividade falam de mensagens vistas, entao passam pelos dois.
    """
    evento = atencao.registrar_hipotese(db, participante, gatilho, 5.0)
    entrega.iniciar_hipotese(db, evento, agora)
    return evento




def test_regras_vem_do_yaml_com_os_cinco_gatilhos(regras):
    chaves = {g.chave for g in regras.gatilhos}
    assert chaves == {
        "nunca_acessou",
        "sem_2fa",
        "prazo_apertado",
        "webconferencia_hoje",
        "certificado_parado",
    }


def test_toda_mensagem_tem_opt_out(db, regras):
    """Nao e cortesia: e o que separa antecipacao de spam institucional."""
    matricula = _matricula_de(db)
    for gatilho in regras.gatilhos:
        texto = gatilhos.montar_mensagem(gatilho, matricula, datetime.now(UTC))
        assert "PARAR" in texto


def test_mensagem_usa_o_nome_e_o_curso(db, regras):
    matricula = _matricula_de(db)
    texto = gatilhos.montar_mensagem(
        regras.por_chave("sem_2fa"), matricula, datetime.now(UTC)
    )
    assert matricula.participante.nome.split()[0] in texto
    assert matricula.curso.titulo in texto


# --------------------------------------------------------------------------
# Avaliacao de condicoes
# --------------------------------------------------------------------------


def test_gatilho_de_2fa_ignora_quem_ja_configurou(db, regras):
    gatilho = regras.por_chave("sem_2fa")
    com_2fa = _matricula_de(db, dois_fatores_configurado=True)
    assert not gatilhos.avaliar(gatilho, com_2fa, datetime.now(UTC))


def test_gatilho_de_2fa_pega_quem_acessou_e_nao_configurou(db, regras):
    gatilho = regras.por_chave("sem_2fa")
    alvo = db.scalars(
        select(Matricula)
        .where(Matricula.dois_fatores_configurado.is_(False))
        .where(Matricula.ultimo_acesso.is_not(None))
    ).first()
    assert gatilhos.avaliar(gatilho, alvo, datetime.now(UTC))


def test_prazo_ja_vencido_nao_dispara(db, regras):
    """Prazo vencido nao e antecipacao, e constrangimento."""
    gatilho = regras.por_chave("prazo_apertado")
    matricula = _matricula_de(db)
    matricula.prazo_pessoal = datetime.now(UTC).date() - timedelta(days=1)
    matricula.progresso = 10
    db.flush()

    assert not gatilhos.avaliar(gatilho, matricula, datetime.now(UTC))


def test_certificado_parado_exige_liberado_e_tempo(db, regras):
    gatilho = regras.por_chave("certificado_parado")
    matricula = _matricula_de(db)
    matricula.situacao_certificado = SituacaoCertificado.LIBERADO
    matricula.ultimo_acesso = datetime.now(UTC) - timedelta(hours=1)
    db.flush()

    assert not gatilhos.avaliar(gatilho, matricula, datetime.now(UTC))

    matricula.ultimo_acesso = datetime.now(UTC) - timedelta(days=4)
    db.flush()
    assert gatilhos.avaliar(gatilho, matricula, datetime.now(UTC))


# --------------------------------------------------------------------------
# Orcamento de atencao
# --------------------------------------------------------------------------


def test_valor_esperado_usa_a_medicao_quando_existe(regras):
    gatilho = regras.por_chave("prazo_apertado")
    estimado = atencao.valor_esperado(gatilho, None)
    medido = atencao.valor_esperado(gatilho, 0.9)

    assert estimado == pytest.approx(
        gatilho.probabilidade_evitar * gatilho.custo_atendimento_min
    )
    assert medido > estimado, "dado observado substitui o chute do YAML"


def test_opt_out_barra_a_mensagem(db, regras, disponivel):
    participante = disponivel
    participante.aceita_avisos = False
    db.flush()

    pode, motivo = atencao.pode_interromper(
        db, participante, regras.por_chave("sem_2fa"), 99
    )
    assert not pode
    assert "nao receber avisos" in motivo


def test_saldo_esgotado_barra_a_mensagem(db, regras, disponivel):
    participante = disponivel
    participante.saldo_atencao = 0
    db.flush()

    pode, motivo = atencao.pode_interromper(
        db, participante, regras.por_chave("sem_2fa"), 99
    )
    assert not pode
    assert "saldo" in motivo


def test_valor_baixo_nao_gasta_orcamento(db, regras, disponivel):
    pode, motivo = atencao.pode_interromper(
        db, disponivel, regras.por_chave("sem_2fa"), 0.1
    )
    assert not pode
    assert "valor esperado" in motivo


def test_mesmo_gatilho_nao_dispara_duas_vezes(db, regras, disponivel):
    participante = disponivel
    gatilho = regras.por_chave("sem_2fa")
    _hipotese_entregue(db, participante, gatilho, datetime.now(UTC))

    pode, motivo = atencao.pode_interromper(db, participante, gatilho, 5.0)
    assert not pode
    assert "ja disparado" in motivo


def test_quem_ignora_recebe_menos(db, regras, disponivel):
    """Quem ignora sistematicamente recebe menos; quem interage, mais."""
    participante = disponivel
    for chave in ("nunca_acessou", "prazo_apertado", "certificado_parado"):
        evento = _hipotese_entregue(
            db, participante, regras.por_chave(chave), datetime.now(UTC)
        )
        evento.efeito = EfeitoAntecipacao.REFUTADO
    db.flush()

    pode, motivo = atencao.pode_interromper(
        db, participante, regras.por_chave("sem_2fa"), 99
    )
    assert not pode
    assert "ignorando" in motivo


def test_eh_optout_reconhece_a_palavra():
    assert atencao.eh_optout("PARAR")
    assert atencao.eh_optout("  parar  ")
    assert not atencao.eh_optout("nao consigo parar de errar a senha")


# --------------------------------------------------------------------------
# Verificacao de efeito: o laco do Andar 1
# --------------------------------------------------------------------------


def _hipotese(db, regras, chave="prazo_apertado", dias_atras=8) -> EventoProativo:
    participante = db.scalars(
        select(Participante).order_by(Participante.email)
    ).first()
    enviado = datetime.now(UTC) - timedelta(days=dias_atras)
    evento = _hipotese_entregue(
        db, participante, regras.por_chave(chave), enviado
    )
    return evento


def test_hipotese_nasce_verificavel(db, regras):
    evento = _hipotese(db, regras, dias_atras=0)
    assert evento.efeito is EfeitoAntecipacao.PENDENTE
    assert "nao abrira atendimento" in evento.hipotese
    assert evento.verificar_em > evento.enviado_em


def test_hipotese_nao_vence_antes_do_prazo(db, regras):
    _hipotese(db, regras, dias_atras=0)
    resultado = atencao.verificar_hipoteses(db)
    assert resultado == {"confirmadas": 0, "refutadas": 0}


def test_sem_atendimento_a_hipotese_e_confirmada(db, regras):
    """Confirmada = o atendimento foi comprovadamente evitado."""
    evento = _hipotese(db, regras)

    atencao.verificar_hipoteses(db)

    assert evento.efeito is EfeitoAntecipacao.CONFIRMADO


def test_atendimento_no_periodo_refuta_a_hipotese(db, regras):
    evento = _hipotese(db, regras)
    caso = Caso(
        participante_id=evento.participante_id,
        canal=Canal.WHATSAPP,
        categoria=Categoria.PRAZO,
        sensivel=False,
        decisao_triagem=DecisaoTriagem.RESPONDE,
        situacao=SituacaoCaso.RESPONDIDO,
    )
    db.add(caso)
    db.flush()
    caso.criado_em = evento.enviado_em + timedelta(days=1)
    db.flush()

    atencao.verificar_hipoteses(db)

    assert evento.efeito is EfeitoAntecipacao.REFUTADO


def test_atendimento_de_outra_categoria_nao_refuta(db, regras):
    """A hipotese e sobre AQUELE assunto, nao sobre a pessoa em geral."""
    evento = _hipotese(db, regras)
    caso = Caso(
        participante_id=evento.participante_id,
        canal=Canal.WHATSAPP,
        categoria=Categoria.CONTEUDO,
        sensivel=False,
        decisao_triagem=DecisaoTriagem.RESPONDE,
        situacao=SituacaoCaso.RESPONDIDO,
    )
    db.add(caso)
    db.flush()
    caso.criado_em = evento.enviado_em + timedelta(days=1)
    db.flush()

    atencao.verificar_hipoteses(db)

    assert evento.efeito is EfeitoAntecipacao.CONFIRMADO


# --------------------------------------------------------------------------
# Desativacao automatica
# --------------------------------------------------------------------------


def _muitas_hipoteses(db, regras, chave, confirmadas, refutadas):
    # A efetividade e agregada sobre a tabela inteira, entao o teste limpa
    # os eventos deste gatilho antes de montar o cenario. Sem isso, uma
    # execucao anterior do motor mudaria o resultado do teste.
    for antigo in db.scalars(
        select(EventoProativo).where(EventoProativo.gatilho == chave)
    ).all():
        db.delete(antigo)
    db.flush()

    participantes = db.scalars(
        select(Participante).order_by(Participante.email)
    ).all()
    total = confirmadas + refutadas
    assert len(participantes) >= total, "seed pequeno demais para o teste"

    for indice in range(total):
        evento = _hipotese_entregue(
            db, participantes[indice], regras.por_chave(chave), datetime.now(UTC)
        )
        evento.efeito = (
            EfeitoAntecipacao.CONFIRMADO
            if indice < confirmadas
            else EfeitoAntecipacao.REFUTADO
        )
    db.flush()


def test_gatilho_fica_em_observacao_ate_ter_amostra(db, regras):
    """Desativar por causa de dois casos seria o erro do banner ao contrario."""
    _muitas_hipoteses(db, regras, "nunca_acessou", confirmadas=0, refutadas=3)

    ativo, motivo = atencao.esta_ativo(db, regras.por_chave("nunca_acessou"))

    assert ativo, "amostra insuficiente nao pode desativar"
    assert "observacao" in motivo


def test_gatilho_inefetivo_e_desativado_automaticamente(db, regras):
    _muitas_hipoteses(db, regras, "nunca_acessou", confirmadas=1, refutadas=14)

    ativo, motivo = atencao.esta_ativo(db, regras.por_chave("nunca_acessou"))

    assert not ativo
    assert "desativado automaticamente" in motivo


def test_gatilho_efetivo_permanece_ativo(db, regras):
    _muitas_hipoteses(db, regras, "nunca_acessou", confirmadas=12, refutadas=2)

    ativo, motivo = atencao.esta_ativo(db, regras.por_chave("nunca_acessou"))

    assert ativo
    assert "efetivo" in motivo


def test_painel_nao_inventa_taxa_sem_amostra(db):
    linhas = {linha["chave"]: linha for linha in antecipacao.painel(db)}
    sem_amostra = [
        linha for linha in linhas.values() if linha["confirmados"] + linha["refutados"] == 0
    ]
    for linha in sem_amostra:
        assert linha["antecipacao_efetiva"] is None


# --------------------------------------------------------------------------
# Entrega diferida: enviar nao e chegar
# --------------------------------------------------------------------------


def test_mensagem_na_fila_nao_conta_como_antecipacao(db, regras, disponivel):
    """O erro que isto trava: creditar efeito a quem nao viu nada.

    Enquanto a mensagem espera na fila, ela nao tem relogio, nao entra na
    medicao e nao pode ser confirmada. Confirmar seria dizer que o gatilho
    evitou um atendimento sem nunca ter falado com a pessoa.
    """
    gatilho = regras.por_chave("sem_2fa")
    antes = atencao.efetividade(db, gatilho.chave)
    evento = atencao.registrar_hipotese(db, disponivel, gatilho, 5.0)

    assert evento.enviado_em is None
    assert evento.verificar_em is None

    # A medicao nao se mexe: enfileirar nao e medir.
    depois = atencao.efetividade(db, gatilho.chave)
    assert depois.amostra == antes.amostra
    assert depois.pendentes == antes.pendentes, "fila nao e amostra"


def test_entrega_inicia_o_relogio_e_debita_a_atencao(db, regras, disponivel):
    gatilho = regras.por_chave("sem_2fa")
    saldo_antes = disponivel.saldo_atencao
    pendentes_antes = atencao.efetividade(db, gatilho.chave).pendentes
    evento = atencao.registrar_hipotese(db, disponivel, gatilho, 5.0)

    agora = datetime.now(UTC)
    entrega.iniciar_hipotese(db, evento, agora)

    assert evento.enviado_em == agora
    assert evento.verificar_em == agora + timedelta(days=regras.janela_dias)
    # Interromper so custa quando de fato interrompe.
    assert disponivel.saldo_atencao == saldo_antes - 1
    assert atencao.efetividade(db, gatilho.chave).pendentes == pendentes_antes + 1


def test_hipotese_sem_relogio_nao_vence(db, regras, disponivel):
    """A verificacao ignora o que ainda nao comecou a contar."""
    evento = atencao.registrar_hipotese(db, disponivel, regras.por_chave("sem_2fa"), 5.0)

    # Prazo absurdo de proposito: nem assim a hipotese sem relogio vence.
    atencao.verificar_hipoteses(db, datetime.now(UTC) + timedelta(days=365))

    assert evento.efeito is EfeitoAntecipacao.PENDENTE
    assert evento.verificar_em is None
