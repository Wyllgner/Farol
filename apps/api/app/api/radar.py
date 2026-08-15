"""Radar de Causas — endpoints do Andar 3."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import AgrupamentoCausa, ArestaJornada, OrdemCorrecao
from app.services import agrupamento, auditoria_jornada, ordem

router = APIRouter(prefix="/radar", tags=["radar"])


def _serializar_ordem(o: OrdemCorrecao, db: Session) -> dict:
    grupo = db.get(AgrupamentoCausa, o.agrupamento_id) if o.agrupamento_id else None
    return {
        "id": str(o.id),
        "hipotese": o.hipotese,
        "evidencia": o.evidencia,
        "acao": o.acao,
        "previsao_queda_mensal": o.previsao_queda_mensal,
        "volume_base_mensal": o.volume_base_mensal,
        "medir_em": o.medir_em.isoformat() if o.medir_em else None,
        "implementada_em": o.implementada_em.isoformat() if o.implementada_em else None,
        "resultado_medido": o.resultado_medido,
        "situacao": str(o.situacao),
        "conclusao": o.conclusao,
        "cursos_afetados": grupo.cursos_afetados if grupo else [],
    }


@router.get("")
def radar(db: Session = Depends(get_db)) -> dict:
    """A UMA ordem em destaque, mais o contexto que a sustenta.

    Tela de recomendacao, nao de grafico: a lista de dez itens e a lista
    que ninguem comeca.
    """
    destaque = ordem.em_destaque(db)
    grupos = db.scalars(
        select(AgrupamentoCausa).order_by(AgrupamentoCausa.volume.desc())
    ).all()

    return {
        "ordem_em_destaque": _serializar_ordem(destaque, db) if destaque else None,
        "agrupamentos": [
            {
                "id": str(g.id),
                "rotulo": g.rotulo,
                "volume": g.volume,
                "cursos_afetados": g.cursos_afetados,
                "aresta": _aresta_legivel(db, g.aresta_origem_id),
            }
            for g in grupos
        ],
        "acerto_das_previsoes": ordem.acerto_das_previsoes(db),
    }


def _aresta_legivel(db: Session, aresta_id) -> str | None:
    if aresta_id is None:
        return None
    aresta = db.get(ArestaJornada, aresta_id)
    return f"{aresta.origem} -> {aresta.destino}" if aresta else None


@router.get("/ordens")
def listar_ordens(db: Session = Depends(get_db)) -> list[dict]:
    """Historico completo, incluindo as hipoteses que foram descartadas."""
    ordens = db.scalars(
        select(OrdemCorrecao).order_by(OrdemCorrecao.criado_em.desc())
    ).all()
    return [_serializar_ordem(o, db) for o in ordens]


@router.post("/analisar")
async def analisar(db: Session = Depends(get_db)) -> dict:
    """Agrupa as demandas e propoe ordens para as causas encontradas."""
    clusters = await agrupamento.agrupar(db)
    propostas = []
    for cluster in clusters:
        proposta = await ordem.propor(db, cluster)
        if proposta is not None:
            propostas.append(_serializar_ordem(proposta, db))
    db.commit()
    return {
        "agrupamentos": [
            {"rotulo": c.rotulo, "volume": c.volume,
             "aresta": c.aresta.origem if c.aresta else None}
            for c in clusters
        ],
        "ordens": propostas,
    }


@router.post("/ordens/{ordem_id}/implementada")
def implementada(ordem_id: str, db: Session = Depends(get_db)) -> dict:
    alvo = db.get(OrdemCorrecao, uuid.UUID(ordem_id))
    if alvo is None:
        raise HTTPException(status_code=404, detail="ordem nao encontrada")
    ordem.marcar_implementada(db, alvo)
    db.commit()
    return _serializar_ordem(alvo, db)


@router.post("/medir")
def medir(db: Session = Depends(get_db)) -> dict:
    """Volta em 30 dias para dizer se a previsao acertou."""
    resultado = ordem.medir(db)
    db.commit()
    return resultado


@router.get("/auditoria-jornada")
def auditar(db: Session = Depends(get_db)) -> dict:
    """Partida a frio: defeitos encontrados sem depender de historico."""
    achados = auditoria_jornada.auditar(db)
    db.commit()
    return {
        "achados": [
            {
                "defeito": a.defeito,
                "documento": a.documento,
                "evidencia": a.evidencia,
                "acao": a.acao,
                "impacto_estimado": a.impacto_estimado,
            }
            for a in achados
        ],
        "total": len(achados),
    }
