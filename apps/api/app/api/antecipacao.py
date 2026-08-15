"""Endpoints do Andar 1 — antecipacao e verificacao de efeito."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.services import antecipacao, atencao, gatilhos

router = APIRouter(prefix="/antecipacao", tags=["antecipacao"])


class EstadoGatilho(BaseModel):
    chave: str
    titulo: str
    ativo: bool
    motivo: str
    enviados: int
    confirmados: int
    refutados: int
    pendentes: int
    # None enquanto nao ha amostra: nao inventamos numero para o painel.
    antecipacao_efetiva: float | None
    valor_esperado: float


@router.get("/gatilhos", response_model=list[EstadoGatilho])
def listar_gatilhos(db: Session = Depends(get_db)):
    """Estado de cada gatilho, com a medicao que decide se ele segue ativo."""
    return antecipacao.painel(db)


@router.post("/rodar")
async def rodar(db: Session = Depends(get_db)) -> dict:
    """Uma passada do motor de antecipacao."""
    resultado = await antecipacao.rodar(db)
    db.commit()
    return resultado


@router.post("/verificar")
def verificar(db: Session = Depends(get_db)) -> dict:
    """Fecha as hipoteses vencidas: o atendimento foi mesmo evitado?"""
    resultado = atencao.verificar_hipoteses(db)
    db.commit()
    return resultado


@router.post("/recarregar-regras")
def recarregar() -> dict:
    """Aplica edicoes no YAML sem reiniciar o processo."""
    regras = gatilhos.recarregar()
    return {
        "gatilhos": [g.chave for g in regras.gatilhos],
        "janela_dias": regras.janela_dias,
        "limiar_efetividade": regras.limiar_efetividade,
    }
