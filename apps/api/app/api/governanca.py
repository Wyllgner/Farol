"""Governanca: Modo Ensaio, indicadores e transparencia de decisao."""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.enums import (
    Categoria,
    ContratoResolucao,
    DecisaoTriagem,
    EfeitoAntecipacao,
    SituacaoCaso,
    SituacaoOrdem,
)
from app.models import (
    Caso,
    DocumentoConhecimento,
    EventoProativo,
    LogAuditoria,
    OrdemCorrecao,
)
from app.seguranca import exigir_admin
from app.services import antecipacao, ensaio, fila, gatilhos, ordem
from app.services.triagem import CONFIANCA_ALTA, CONFIANCA_MEDIA, TEXTO_RECUSA

router = APIRouter(tags=["governanca"])


# --------------------------------------------------------------------------
# Modo Ensaio: superficie restrita
#
# Liberar uma categoria autoriza o FAROL a falar em nome da Escola sem
# revisao humana. E a decisao de maior consequencia do produto inteiro,
# entao ela nao fica atras de um botao publico: exige token.
# --------------------------------------------------------------------------


class Liberacao(BaseModel):
    servidor: str = Field(min_length=1, max_length=200)


class Revisao(BaseModel):
    servidor: str = Field(min_length=1, max_length=200)
    aprovado: bool


@router.get("/ensaio", dependencies=[Depends(exigir_admin)])
def estado_do_ensaio(db: Session = Depends(get_db)) -> dict:
    linhas = ensaio.desempenho(db)
    return {
        "modo_ensaio_ativo": ensaio.ativo(),
        "taxa_para_liberar": ensaio.TAXA_PARA_LIBERAR,
        "amostra_minima": ensaio.AMOSTRA_MINIMA,
        "categorias": [
            {
                "categoria": str(d.categoria),
                "revisados": d.revisados,
                "aprovados": d.aprovados,
                "taxa_acerto": d.taxa_acerto,
                "liberada": d.liberada,
                "pode_liberar": d.pode_liberar,
            }
            for d in linhas
        ],
    }


@router.post("/ensaio/{categoria}/liberar", dependencies=[Depends(exigir_admin)])
def liberar(categoria: Categoria, dados: Liberacao, db: Session = Depends(get_db)) -> dict:
    """Libera uma categoria para resposta automatica.

    A decisao e humana e explicita: o sistema mostra a taxa de acerto, mas
    quem autoriza o FAROL a falar em nome da Escola e uma pessoa.
    """
    registro = ensaio.liberar(db, categoria, dados.servidor)
    db.commit()
    return {"categoria": str(categoria), "liberada": registro.liberada}


@router.post("/ensaio/{categoria}/recolher", dependencies=[Depends(exigir_admin)])
def recolher(categoria: Categoria, dados: Liberacao, db: Session = Depends(get_db)) -> dict:
    ensaio.recolher(db, categoria, dados.servidor)
    db.commit()
    return {"categoria": str(categoria), "liberada": False}


@router.post("/ensaio/caso/{caso_id}/revisar", dependencies=[Depends(exigir_admin)])
def revisar(caso_id: str, dados: Revisao, db: Session = Depends(get_db)) -> dict:
    caso = fila.obter(db, uuid.UUID(caso_id))
    if caso is None:
        raise HTTPException(status_code=404, detail="caso nao encontrado")
    ensaio.registrar_revisao(db, caso, dados.aprovado, dados.servidor)
    db.commit()
    return {"caso": caso_id, "aprovado": dados.aprovado}


# --------------------------------------------------------------------------
# Indicadores: a metrica invertida
# --------------------------------------------------------------------------


@router.get("/indicadores")
def indicadores(db: Session = Depends(get_db)) -> dict:
    """Sucesso, aqui, e este painel diminuir.

    Todo painel de chatbot comemora quando o numero de conversas sobe. O
    do FAROL comemora quando desce, porque significa que as causas estao
    sendo eliminadas.
    """
    total_casos = db.scalar(select(func.count(Caso.id))) or 0
    # Escalar nao e resolver sem humano. O filtro por decisao existe
    # porque um caso escalado tambem termina ENCERRADO depois que o
    # servidor o atende: conta-lo aqui creditaria ao FAROL um trabalho
    # que uma pessoa fez, e esta e justamente a metrica que a banca vai
    # querer conferir.
    resolvidos_sem_humano = (
        db.scalar(
            select(func.count(Caso.id)).where(
                Caso.situacao.in_([SituacaoCaso.RESPONDIDO, SituacaoCaso.ENCERRADO]),
                Caso.em_ensaio.is_(False),
                Caso.decisao_triagem.is_not(None),
                Caso.decisao_triagem != DecisaoTriagem.ESCALA,
            )
        )
        or 0
    )

    confirmados = (
        db.scalar(
            select(func.count(EventoProativo.id)).where(
                EventoProativo.efeito == EfeitoAntecipacao.CONFIRMADO
            )
        )
        or 0
    )
    refutados = (
        db.scalar(
            select(func.count(EventoProativo.id)).where(
                EventoProativo.efeito == EfeitoAntecipacao.REFUTADO
            )
        )
        or 0
    )
    verificados = confirmados + refutados

    contratos = dict(
        db.execute(
            select(Caso.contrato_resolucao, func.count(Caso.id)).group_by(
                Caso.contrato_resolucao
            )
        ).all()
    )
    fechados = contratos.get(ContratoResolucao.CONFIRMADO, 0)
    falhados = contratos.get(ContratoResolucao.FALHOU, 0)
    respondidos = fechados + falhados

    # Minutos por atendimento evitado, conforme o custo declarado no YAML.
    custo_medio = sum(
        g.custo_atendimento_min for g in gatilhos.carregar().gatilhos
    ) / max(1, len(gatilhos.carregar().gatilhos))

    metricas_ordem = ordem.acerto_das_previsoes(db)

    return {
        # A metrica invertida vem primeiro, de proposito.
        "atendimentos_evitados": confirmados,
        "horas_devolvidas_a_equipe": round(confirmados * custo_medio / 60, 1),
        "causas_extintas": metricas_ordem.get("causas_extintas", 0),
        "taxa_antecipacao_efetiva": (
            round(confirmados / verificados, 4) if verificados else None
        ),
        "taxa_resolucao_sem_humano": (
            round(resolvidos_sem_humano / total_casos, 4) if total_casos else None
        ),
        "taxa_confirmacao_resolucao": (
            round(fechados / respondidos, 4) if respondidos else None
        ),
        "acerto_das_previsoes": metricas_ordem.get("acerto"),
        "total_de_casos": total_casos,
        "na_fila": fila.metricas(db)["na_fila"],
        # Meta: zero. E o numero que a tela de transparencia publica.
        "respostas_sem_fonte": db.scalar(
            select(func.count(LogAuditoria.id)).where(
                LogAuditoria.etapa == "resposta_sem_fonte"
            )
        )
        or 0,
    }


# --------------------------------------------------------------------------
# Como o FAROL decide
# --------------------------------------------------------------------------


@router.get("/como-decide", dependencies=[Depends(exigir_admin)])
def como_decide(db: Session = Depends(get_db)) -> dict:
    """A politica de decisao, publicada.

    O sistema nao e caixa-preta nem para o servidor nem para o gestor: a
    mesma tabela que o codigo executa e a que aparece aqui.
    """
    regras = gatilhos.carregar()
    documentos = db.scalars(select(DocumentoConhecimento)).all()

    return {
        "politica_de_triagem": [
            {
                "situacao": "Confianca alta e assunto nao sensivel",
                "criterio": f"confianca >= {CONFIANCA_ALTA}",
                "acao": "Responde direto",
            },
            {
                "situacao": "Confianca media",
                "criterio": f"{CONFIANCA_MEDIA} <= confianca < {CONFIANCA_ALTA}",
                "acao": "Responde e oferece falar com humano",
            },
            {
                "situacao": "Confianca baixa ou sem fonte",
                "criterio": f"confianca < {CONFIANCA_MEDIA} ou NAO_SEI",
                "acao": "Recusa e escala com dossie",
            },
            {
                "situacao": "Categoria sensivel",
                "criterio": "dado pessoal, reclamacao, saude, financeiro, urgencia",
                "acao": "Escala sempre, independentemente da confianca",
            },
        ],
        "texto_da_recusa": TEXTO_RECUSA,
        "gatilhos": antecipacao.painel(db),
        "regras_do_grafo": {
            "janela_de_verificacao_dias": regras.janela_dias,
            "limiar_de_efetividade": regras.limiar_efetividade,
            "amostra_minima": regras.amostra_minima,
            "saldo_de_atencao_inicial": regras.saldo_inicial,
        },
        "conhecimento": {
            "documentos_vigentes": sum(1 for d in documentos if d.situacao == "vigente"),
            "documentos_vencidos": sum(1 for d in documentos if d.situacao == "vencido"),
            "aprovados_por_servidor": sum(1 for d in documentos if d.aprovado_por_servidor),
        },
        "modelo": {
            "classificacao": settings.llm_model_classificacao,
            "geracao": settings.llm_model_geracao,
            "modo_ensaio": settings.modo_ensaio,
        },
    }


# --------------------------------------------------------------------------
# Series: a curva, nao o instante
# --------------------------------------------------------------------------


@router.get("/indicadores/series")
def series(semanas: int = 12, db: Session = Depends(get_db)) -> dict:
    """As mesmas metricas do painel, ao longo do tempo.

    O numero de hoje diz onde estamos; so a serie diz para onde estamos
    indo, e a tese do FAROL e inteira sobre direcao: o painel tem que
    DESCER. Um cartao com "737 casos" nao consegue afirmar isso.

    Tudo aqui e agregado por consulta sobre as tabelas de operacao. Nao
    ha valor escrito na tela: se a curva subir, o painel mostra subindo.
    """
    semanas = max(4, min(52, semanas))
    agora = datetime.now(UTC)

    # A serie termina na ultima semana FECHADA. A semana em curso tem
    # dois dias de dado onde as outras tem sete, e plotada ao lado delas
    # ela desenha uma queda que nao aconteceu: seria o proprio painel
    # produzindo a evidencia que o produto promete medir. O movimento de
    # hoje aparece nos cartoes, que sao contadores, nao tendencia.
    dias_desde_segunda = agora.weekday()
    fim = (agora - timedelta(days=dias_desde_segunda)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    inicio = fim - timedelta(weeks=semanas)

    def indice(quando: datetime) -> int | None:
        """Em qual balde semanal esta data cai. None se estiver fora."""
        if quando is None:
            return None
        if quando.tzinfo is None:
            quando = quando.replace(tzinfo=UTC)
        if quando < inicio or quando >= fim:
            return None
        return min(semanas - 1, int((quando - inicio).days // 7))

    rotulos = [
        (inicio + timedelta(weeks=i)).strftime("%d/%m") for i in range(semanas)
    ]

    # --- volume semanal: o que chegou x o que foi evitado ---
    chegaram = [0] * semanas
    resolvidos = [0] * semanas
    escalados = [0] * semanas
    for criado_em, decisao in db.execute(
        select(Caso.criado_em, Caso.decisao_triagem).where(
            Caso.criado_em >= inicio, Caso.criado_em < fim
        )
    ).all():
        i = indice(criado_em)
        if i is None:
            continue
        chegaram[i] += 1
        if decisao is DecisaoTriagem.ESCALA:
            escalados[i] += 1
        elif decisao is not None:
            resolvidos[i] += 1

    evitados = [0] * semanas
    refutados = [0] * semanas
    for enviado_em, efeito in db.execute(
        select(EventoProativo.enviado_em, EventoProativo.efeito).where(
            EventoProativo.enviado_em.is_not(None)
        )
    ).all():
        i = indice(enviado_em)
        if i is None:
            continue
        if efeito == EfeitoAntecipacao.CONFIRMADO:
            evitados[i] += 1
        elif efeito == EfeitoAntecipacao.REFUTADO:
            refutados[i] += 1

    # --- volume por categoria: onde a queda aconteceu ---
    por_categoria: dict[str, list[int]] = {}
    for criado_em, categoria in db.execute(
        select(Caso.criado_em, Caso.categoria).where(
            Caso.criado_em >= inicio, Caso.criado_em < fim
        )
    ).all():
        i = indice(criado_em)
        if i is None:
            continue
        serie = por_categoria.setdefault(str(categoria), [0] * semanas)
        serie[i] += 1

    # So as quatro categorias de maior volume viram linha. As demais somam
    # em "outras": uma nona cor nao existe, e um grafico com doze linhas
    # nao e um grafico, e uma meada.
    ranking = sorted(por_categoria.items(), key=lambda kv: sum(kv[1]), reverse=True)
    destaques = ranking[:4]
    resto = ranking[4:]
    categorias = [{"categoria": nome, "valores": v} for nome, v in destaques]
    if resto:
        outras = [sum(v[i] for _, v in resto) for i in range(semanas)]
        categorias.append({"categoria": "outras", "valores": outras})

    # --- ordens: previsao contra medicao ---
    ordens_medidas = [
        {
            "acao": o.acao,
            "previsto": o.previsao_queda_mensal,
            "medido": o.resultado_medido,
            "acertou": o.situacao is SituacaoOrdem.CONFIRMADA,
        }
        for o in db.scalars(
            select(OrdemCorrecao)
            .where(OrdemCorrecao.resultado_medido.is_not(None))
            .order_by(OrdemCorrecao.criado_em)
        ).all()
    ]

    # --- destino dos casos: para onde a triagem mandou cada um ---
    destino = dict(
        db.execute(
            select(Caso.decisao_triagem, func.count(Caso.id))
            .where(Caso.decisao_triagem.is_not(None))
            .group_by(Caso.decisao_triagem)
        ).all()
    )

    return {
        "semanas": rotulos,
        "ate": fim.date().isoformat(),
        "volume": {
            "chegaram": chegaram,
            "evitados": evitados,
            "refutados": refutados,
            "resolvidos_sem_humano": resolvidos,
            "escalados": escalados,
        },
        "por_categoria": categorias,
        "ordens_medidas": ordens_medidas,
        "destino_dos_casos": [
            {"decisao": str(d), "total": t} for d, t in destino.items()
        ],
    }
