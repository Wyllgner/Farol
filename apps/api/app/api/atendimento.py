"""Endpoint de atendimento — o motor unico, independente de canal."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.enums import Canal
from app.services.atendimento import atender

router = APIRouter(tags=["atendimento"])


class Mensagem(BaseModel):
    canal: Canal = Canal.WHATSAPP
    # Identificador no canal: telefone, e-mail ou sessao do widget.
    # Vazio significa anonimo, e o produto continua util assim.
    handle: str = ""
    pergunta: str = Field(min_length=1, max_length=2000)


class FonteExibida(BaseModel):
    documento: str
    dono: str
    score: float


class Resposta(BaseModel):
    resposta: str
    categoria: str
    # Toda resposta mostra de onde veio (secao 12.2, item 6).
    fontes: list[FonteExibida]
    acoes_rapidas: list[str]
    # Transparencia de decisao: por que respondeu ou por que escalou.
    decisao: str
    motivo: str
    confianca: float
    escalou: bool
    nivel_identidade: str
    caso_id: str | None


@router.post("/atendimento", response_model=Resposta)
async def receber(mensagem: Mensagem, db: Session = Depends(get_db)) -> Resposta:
    resultado = await atender(
        db,
        canal=mensagem.canal,
        handle=mensagem.handle,
        pergunta=mensagem.pergunta,
    )
    db.commit()

    return Resposta(
        resposta=resultado.resposta,
        categoria=str(resultado.categoria),
        fontes=[
            FonteExibida(documento=t["documento"], dono=t["dono"], score=t["score"])
            for t in resultado.trechos
        ],
        acoes_rapidas=resultado.acoes_rapidas,
        decisao=str(resultado.decisao.decisao),
        motivo=resultado.decisao.motivo,
        confianca=resultado.decisao.confianca,
        escalou=resultado.escalou,
        nivel_identidade=str(resultado.identidade.nivel),
        caso_id=str(resultado.caso.id) if resultado.caso else None,
    )
