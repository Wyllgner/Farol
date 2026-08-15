"""Endpoints da fila do servidor."""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.services import fila, laco

router = APIRouter(prefix="/fila", tags=["fila"])


class ItemFila(BaseModel):
    id: str
    categoria: str
    canal: str
    sensivel: bool
    situacao: str
    score_consequencia: float
    orientacao_padrao_falhou: bool
    contrato_resolucao: str
    resumo: str
    criado_em: str
    # Cronometro: ha quanto tempo o caso espera.
    minutos_esperando: int
    assumido_por: str | None
    dossie: dict | None
    rascunho_resposta: str | None


class Metricas(BaseModel):
    na_fila: int
    encerrados: int
    com_orientacao_padrao_falha: int
    sensiveis: int


class Assumir(BaseModel):
    servidor: str = Field(min_length=1, max_length=200)


class Responder(BaseModel):
    servidor: str = Field(min_length=1, max_length=200)
    texto: str = Field(min_length=1)


class Aprovar(BaseModel):
    servidor: str = Field(min_length=1, max_length=200)
    titulo: str = Field(min_length=3, max_length=300)
    conteudo: str | None = None


def _serializar(caso) -> ItemFila:
    referencia = caso.assumido_em or caso.criado_em
    espera = datetime.now(UTC) - referencia
    dossie = caso.dossie or {}
    return ItemFila(
        id=str(caso.id),
        categoria=str(caso.categoria),
        canal=str(caso.canal),
        sensivel=caso.sensivel,
        situacao=str(caso.situacao),
        score_consequencia=float(caso.score_consequencia or 0),
        orientacao_padrao_falhou=caso.orientacao_padrao_falhou,
        contrato_resolucao=str(caso.contrato_resolucao),
        resumo=dossie.get("resumo", "(sem resumo)"),
        criado_em=caso.criado_em.isoformat(),
        minutos_esperando=max(0, int(espera.total_seconds() // 60)),
        assumido_por=caso.assumido_por,
        dossie=caso.dossie,
        rascunho_resposta=caso.rascunho_resposta,
    )


def _obter(db: Session, caso_id: str):
    caso = fila.obter(db, uuid.UUID(caso_id))
    if caso is None:
        raise HTTPException(status_code=404, detail="caso nao encontrado")
    return caso


@router.get("", response_model=list[ItemFila])
def listar(incluir_encerrados: bool = False, db: Session = Depends(get_db)):
    return [_serializar(c) for c in fila.listar(db, incluir_encerrados)]


@router.get("/metricas", response_model=Metricas)
def metricas(db: Session = Depends(get_db)) -> Metricas:
    return Metricas(**fila.metricas(db))


@router.post("/{caso_id}/assumir", response_model=ItemFila)
def assumir(caso_id: str, dados: Assumir, db: Session = Depends(get_db)):
    caso = fila.assumir(db, _obter(db, caso_id), dados.servidor)
    db.commit()
    return _serializar(caso)


@router.post("/{caso_id}/responder", response_model=ItemFila)
def responder(caso_id: str, dados: Responder, db: Session = Depends(get_db)):
    """Envia o texto revisado pelo servidor. Nada sai sem essa revisao."""
    caso = fila.responder(db, _obter(db, caso_id), dados.texto, dados.servidor)
    db.commit()
    return _serializar(caso)


@router.post("/{caso_id}/aprovar-conhecimento")
async def aprovar(caso_id: str, dados: Aprovar, db: Session = Depends(get_db)):
    """Transforma a resposta do servidor em fonte oficial citavel."""
    caso = _obter(db, caso_id)
    try:
        documento = await fila.aprovar_como_conhecimento(
            db, caso, dados.titulo, dados.servidor, dados.conteudo
        )
    except ValueError as erro:
        raise HTTPException(status_code=400, detail=str(erro)) from erro
    db.commit()
    return {
        "documento_id": str(documento.id),
        "titulo": documento.titulo,
        "valido_ate": documento.valido_ate.isoformat(),
    }


@router.post("/laco/contratos")
async def rodar_contratos(db: Session = Depends(get_db)) -> dict:
    """Dispara a verificacao do Contrato de Resolucao.

    O agendador chama exatamente isto; o console de demonstracao tambem.
    Um caminho so, para que o que se demonstra seja o que roda.
    """
    resultado = await laco.rodar_contratos(db)
    db.commit()
    return resultado
