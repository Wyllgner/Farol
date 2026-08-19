"""Console de Demonstracao: controle do mundo ficticio.

Todos os disparos aqui reutilizam as funcoes de producao. O console
existe para dar um botao a elas, nao para criar um caminho paralelo.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.services import antecipacao, atencao, demo, laco, ordem

router = APIRouter(prefix="/demo", tags=["demonstracao"])


class AvancarTempo(BaseModel):
    dias: int = Field(ge=1, le=365)


class AlternarEnsaio(BaseModel):
    ativo: bool


@router.get("/estado")
def estado(db: Session = Depends(get_db)) -> dict:
    return demo.estado(db)


@router.get("/cenarios")
def cenarios(db: Session = Depends(get_db)) -> list[dict]:
    """Participantes por estado, para achar em um clique quem aciona o quê."""
    return [
        {
            "telefone": c.telefone,
            "nome": c.nome,
            "curso": c.curso,
            "rotulo": c.rotulo,
            "detalhe": c.detalhe,
        }
        for c in demo.cenarios(db)
    ]


@router.post("/avancar-tempo")
async def avancar_tempo(dados: AvancarTempo, db: Session = Depends(get_db)) -> dict:
    """Move o relogio e roda os lacos que vencerem no caminho.

    Avancar o tempo sem executar as verificacoes deixaria o mundo em um
    estado que nunca existiria de verdade.
    """
    try:
        movimento = demo.avancar_tempo(db, dados.dias)
    except ValueError as erro:
        raise HTTPException(status_code=400, detail=str(erro)) from erro

    contratos = await laco.rodar_contratos(db)
    hipoteses = atencao.verificar_hipoteses(db)
    medicoes = ordem.medir(db)
    db.commit()

    return {
        "tempo": movimento,
        "contratos": contratos,
        "hipoteses": hipoteses,
        "ordens_medidas": medicoes,
    }


@router.post("/modo-ensaio")
def modo_ensaio(dados: AlternarEnsaio, db: Session = Depends(get_db)) -> dict:
    resultado = demo.alternar_ensaio(db, dados.ativo)
    db.commit()
    return resultado


@router.post("/disparar-gatilhos")
async def disparar_gatilhos(db: Session = Depends(get_db)) -> dict:
    """Mesma funcao que o agendador chamaria."""
    resultado = await antecipacao.rodar(db)
    db.commit()
    return resultado


@router.post("/restaurar-saldos")
def restaurar_saldos(db: Session = Depends(get_db)) -> dict:
    """Devolve o orcamento de atencao para poder ensaiar de novo."""
    resultado = demo.restaurar_saldos(db)
    db.commit()
    return resultado


@router.post("/resetar")
async def resetar() -> dict:
    """Recria o mundo ficticio do zero.

    Semente fixa: o reset e idempotente e a demonstracao nunca falha por
    estado sujo de um ensaio anterior.
    """
    from app.seed import semear

    return await semear()
