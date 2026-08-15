"""Governanca: Modo Ensaio, indicadores e transparencia de decisao."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.enums import Categoria, ContratoResolucao, EfeitoAntecipacao, SituacaoCaso
from app.models import Caso, DocumentoConhecimento, EventoProativo, LogAuditoria
from app.services import antecipacao, ensaio, fila, gatilhos, ordem
from app.services.triagem import CONFIANCA_ALTA, CONFIANCA_MEDIA, TEXTO_RECUSA

router = APIRouter(tags=["governanca"])


# --------------------------------------------------------------------------
# Modo Ensaio
# --------------------------------------------------------------------------


class Liberacao(BaseModel):
    servidor: str = Field(min_length=1, max_length=200)


class Revisao(BaseModel):
    servidor: str = Field(min_length=1, max_length=200)
    aprovado: bool


@router.get("/ensaio")
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


@router.post("/ensaio/{categoria}/liberar")
def liberar(categoria: Categoria, dados: Liberacao, db: Session = Depends(get_db)) -> dict:
    """Libera uma categoria para resposta automatica.

    A decisao e humana e explicita: o sistema mostra a taxa de acerto, mas
    quem autoriza o FAROL a falar em nome da Escola e uma pessoa.
    """
    registro = ensaio.liberar(db, categoria, dados.servidor)
    db.commit()
    return {"categoria": str(categoria), "liberada": registro.liberada}


@router.post("/ensaio/{categoria}/recolher")
def recolher(categoria: Categoria, dados: Liberacao, db: Session = Depends(get_db)) -> dict:
    ensaio.recolher(db, categoria, dados.servidor)
    db.commit()
    return {"categoria": str(categoria), "liberada": False}


@router.post("/ensaio/caso/{caso_id}/revisar")
def revisar(caso_id: str, dados: Revisao, db: Session = Depends(get_db)) -> dict:
    caso = fila.obter(db, uuid.UUID(caso_id))
    if caso is None:
        raise HTTPException(status_code=404, detail="caso nao encontrado")
    ensaio.registrar_revisao(db, caso, dados.aprovado, dados.servidor)
    db.commit()
    return {"caso": caso_id, "aprovado": dados.aprovado}


# --------------------------------------------------------------------------
# Indicadores — a metrica invertida
# --------------------------------------------------------------------------


@router.get("/indicadores")
def indicadores(db: Session = Depends(get_db)) -> dict:
    """Sucesso, aqui, e este painel diminuir.

    Todo painel de chatbot comemora quando o numero de conversas sobe. O
    do FAROL comemora quando desce, porque significa que as causas estao
    sendo eliminadas.
    """
    total_casos = db.scalar(select(func.count(Caso.id))) or 0
    resolvidos_sem_humano = (
        db.scalar(
            select(func.count(Caso.id)).where(
                Caso.situacao.in_([SituacaoCaso.RESPONDIDO, SituacaoCaso.ENCERRADO]),
                Caso.em_ensaio.is_(False),
                Caso.decisao_triagem.is_not(None),
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


@router.get("/como-decide")
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
