from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api import atendimento, busca, canal, fila
from app.config import settings
from app.db import engine
from app.llm import obter_provider

app = FastAPI(
    title="FAROL v2 — API",
    description="Fluxo de Atendimento, Resolucao e Orientacao em Laco — SECOEAD/EMERON",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.web_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(busca.router)
app.include_router(atendimento.router)
app.include_router(canal.router)
app.include_router(fila.router)


@app.get("/health")
def health() -> dict:
    """Diz a verdade sobre o estado do sistema, inclusive quando degradado."""
    try:
        with engine.connect() as conexao:
            conexao.execute(text("SELECT 1"))
        banco = "ok"
    except Exception as erro:  # noqa: BLE001 — health check nunca deve derrubar o processo
        banco = f"erro: {erro.__class__.__name__}"

    provider = obter_provider()
    return {
        "servico": "farol-api",
        "banco": banco,
        "llm": provider.nome,
        # Os dois papeis aparecem separados porque podem divergir: a tela
        # "Como o FAROL decide" (secao 7.3) mostra com que modelo cada
        # etapa rodou, e degradado nao pode passar por normal.
        "modelo_classificacao": settings.llm_model_classificacao,
        "modelo_geracao": settings.llm_model_geracao,
        "degradado": provider.nome == "fallback",
        "embeddings": settings.embedding_provider,
        "canal": settings.channel_adapter,
        "modo_ensaio": settings.modo_ensaio,
    }
