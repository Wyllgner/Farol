"""Recuperacao semantica na base oficial."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.conhecimento import buscar

router = APIRouter(tags=["conhecimento"])


class Consulta(BaseModel):
    pergunta: str = Field(min_length=1, max_length=2000)
    limite: int = Field(default=4, ge=1, le=10)


class Trecho(BaseModel):
    id: str
    texto: str
    documento: str
    dono: str
    valido_ate: str | None
    score: float


class Resultado(BaseModel):
    trechos: list[Trecho]
    # Zero trechos nao e falha: e o caso em que o FAROL escala em vez de
    # responder. A tela de transparencia mostra isso como recusa, nao erro.
    tem_fonte: bool


@router.post("/search", response_model=Resultado)
async def search(consulta: Consulta, db: Session = Depends(get_db)) -> Resultado:
    trechos = await buscar(db, consulta.pergunta, limite=consulta.limite)
    db.commit()
    return Resultado(trechos=trechos, tem_fonte=bool(trechos))
