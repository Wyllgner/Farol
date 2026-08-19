"""Testes do Andar 3: causa-raiz, ordens de correcao e auditoria a frio.

O que precisa ficar provado: a ordem carrega previsao numerica, a
previsao e conferida na data marcada, e a hipotese que falha e
DESCARTADA com o motivo registrado. Um Andar 3 que so acumulasse
sugestoes sem medir seria o banner de novo, em formato de dashboard.
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.db import SessionLocal
from app.enums import Canal, Categoria, DecisaoTriagem, SituacaoCaso, SituacaoOrdem
from app.models import AgrupamentoCausa, ArestaJornada, Caso, OrdemCorrecao
from app.services import agrupamento, auditoria_jornada, ordem
from app.services.agrupamento import Cluster


@pytest.fixture
def db():
    with SessionLocal() as sessao:
        yield sessao
        sessao.rollback()


def _caso(db, categoria=Categoria.WEBCONFERENCIA, pergunta="nao acho o link") -> Caso:
    registro = Caso(
        canal=Canal.WHATSAPP,
        categoria=categoria,
        sensivel=False,
        decisao_triagem=DecisaoTriagem.RESPONDE,
        situacao=SituacaoCaso.RESPONDIDO,
        pergunta=pergunta,
    )
    db.add(registro)
    db.flush()
    return registro


def _cluster(db, volume=6, dias_atras=60) -> Cluster:
    aresta = db.scalar(
        select(ArestaJornada).where(ArestaJornada.origem == "consumo_conteudo")
    )
    grupo = AgrupamentoCausa(
        rotulo="nao encontram o link da webconferencia",
        volume=volume,
        aresta_origem_id=aresta.id if aresta else None,
        cursos_afetados=["Curso A"],
    )
    db.add(grupo)
    db.flush()

    casos = []
    for _ in range(volume):
        c = _caso(db)
        c.agrupamento_id = grupo.id
        # Os casos que motivaram a ordem sao ANTERIORES a correcao. Cria-los
        # "agora" e depois datar a implementacao no passado faria o proprio
        # sintoma contar como reincidencia.
        c.criado_em = datetime.now(UTC) - timedelta(days=dias_atras)
        casos.append(c)
    db.flush()

    return Cluster(
        id=grupo.id,
        rotulo=grupo.rotulo,
        casos=casos,
        aresta=aresta,
        cursos=["Curso A"],
    )


# --------------------------------------------------------------------------
# Ordem de correcao
# --------------------------------------------------------------------------


async def test_ordem_nasce_com_previsao_numerica(db):
    proposta = await ordem.propor(db, _cluster(db))

    assert proposta is not None
    assert proposta.previsao_queda_mensal > 0
    assert proposta.volume_base_mensal == 6
    assert proposta.hipotese and proposta.evidencia and proposta.acao
    assert proposta.situacao is SituacaoOrdem.PENDENTE


async def test_evidencia_cita_volume_e_aresta(db):
    proposta = await ordem.propor(db, _cluster(db))

    assert "6 casos" in proposta.evidencia
    assert "consumo_conteudo" in proposta.evidencia


async def test_acao_e_especifica_da_aresta(db):
    """Acao generica nao ajuda ninguem a corrigir nada."""
    proposta = await ordem.propor(db, _cluster(db))
    assert "webconferencia" in proposta.acao.lower()


async def test_nao_duplica_ordem_para_o_mesmo_agrupamento(db):
    cluster = _cluster(db)
    primeira = await ordem.propor(db, cluster)
    segunda = await ordem.propor(db, cluster)
    assert primeira.id == segunda.id


async def test_previsao_e_conservadora(db):
    """Prever demais e a forma mais rapida de perder credibilidade."""
    proposta = await ordem.propor(db, _cluster(db, volume=10))
    assert proposta.previsao_queda_mensal < 10


# --------------------------------------------------------------------------
# Medicao: o laco
# --------------------------------------------------------------------------


async def test_nao_mede_antes_da_data(db):
    proposta = await ordem.propor(db, _cluster(db))
    ordem.marcar_implementada(db, proposta)

    resultado = ordem.medir(db)

    assert resultado == {"confirmadas": 0, "descartadas": 0}
    assert proposta.situacao is SituacaoOrdem.IMPLEMENTADA


async def test_medicao_define_a_data_a_partir_da_implementacao(db):
    proposta = await ordem.propor(db, _cluster(db))
    assert proposta.medir_em is None, "sem implementacao nao ha o que medir"

    hoje = datetime.now(UTC).date()
    ordem.marcar_implementada(db, proposta, quando=hoje)

    assert proposta.implementada_em == hoje
    assert proposta.medir_em == hoje + ordem.JANELA_MEDICAO


async def test_queda_confirmada_extingue_a_causa(db):
    proposta = await ordem.propor(db, _cluster(db))
    # Implementada no passado, com os casos todos anteriores: o volume
    # depois da implementacao e zero.
    ordem.marcar_implementada(
        db, proposta, quando=datetime.now(UTC).date() - timedelta(days=40)
    )

    resultado = ordem.medir(db)

    assert resultado["confirmadas"] == 1
    assert proposta.situacao is SituacaoOrdem.CONFIRMADA
    assert "Causa extinta" in proposta.conclusao


async def test_hipotese_que_falha_e_descartada(db):
    """O sistema nao esconde as proprias hipoteses erradas."""
    cluster = _cluster(db)
    proposta = await ordem.propor(db, cluster)
    ordem.marcar_implementada(
        db, proposta, quando=datetime.now(UTC).date() - timedelta(days=40)
    )

    # O volume nao caiu: novos casos continuam chegando depois da correcao.
    for _ in range(6):
        novo = _caso(db)
        novo.agrupamento_id = proposta.agrupamento_id
    db.flush()

    resultado = ordem.medir(db)

    assert resultado["descartadas"] == 1
    assert proposta.situacao is SituacaoOrdem.DESCARTADA
    assert "descartada" in proposta.conclusao.lower()
    assert "outra causa" in proposta.conclusao


async def test_acerto_das_previsoes_e_publicado(db):
    proposta = await ordem.propor(db, _cluster(db))
    ordem.marcar_implementada(
        db, proposta, quando=datetime.now(UTC).date() - timedelta(days=40)
    )
    ordem.medir(db)

    metricas = ordem.acerto_das_previsoes(db)

    assert metricas["medidas"] >= 1
    assert metricas["acerto"] is not None


def test_sem_medicao_nao_inventa_taxa(db):
    for antiga in db.scalars(select(OrdemCorrecao)).all():
        db.delete(antiga)
    db.flush()

    assert ordem.acerto_das_previsoes(db) == {"medidas": 0, "acerto": None}


# --------------------------------------------------------------------------
# Uma ordem por vez
# --------------------------------------------------------------------------


async def test_destaque_traz_a_de_maior_impacto(db):
    for antiga in db.scalars(select(OrdemCorrecao)).all():
        db.delete(antiga)
    db.flush()

    pequena = await ordem.propor(db, _cluster(db, volume=4))
    grande = await ordem.propor(db, _cluster(db, volume=20))

    destaque = ordem.em_destaque(db)

    assert destaque.id == grande.id
    assert destaque.id != pequena.id


# --------------------------------------------------------------------------
# Agrupamento
# --------------------------------------------------------------------------


async def test_poucos_casos_nao_viram_causa(db, monkeypatch):
    """Abaixo do minimo nao ha padrao, ha coincidencia."""
    monkeypatch.setattr(
        agrupamento, "_casos_analisaveis", lambda _: [_caso(db)]
    )
    assert await agrupamento.agrupar(db) == []


def test_concentracao_em_um_curso(db):
    cluster = _cluster(db)
    curso, concentracao = agrupamento.concentracao_em_um_curso(cluster, db)
    # Casos sem participante nao tem curso: a funcao devolve vazio em vez
    # de inventar concentracao.
    assert concentracao == 0.0
    assert curso == ""


# --------------------------------------------------------------------------
# Auditoria de jornada: partida a frio
# --------------------------------------------------------------------------


def test_auditoria_encontra_defeitos_sem_historico(db):
    """Gera valor antes do primeiro atendimento."""
    achados = auditoria_jornada.auditar(db)

    assert achados, "a base semeada tem defeitos plantados de proposito"
    for achado in achados:
        assert achado.defeito and achado.acao
        assert achado.impacto_estimado > 0


def test_auditoria_detecta_falta_de_caminho_para_suporte(db):
    achados = auditoria_jornada.auditar(db)
    defeitos = {a.defeito for a in achados}
    assert "pagina sem caminho visivel para suporte" in defeitos


def test_auditoria_ordena_por_impacto(db):
    achados = auditoria_jornada.auditar(db)
    impactos = [a.impacto_estimado for a in achados]
    assert impactos == sorted(impactos, reverse=True)
