import logging
import time
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.api import (
    antecipacao,
    atendimento,
    busca,
    canal,
    demo,
    fila,
    governanca,
    radar,
)
from app.config import settings
from app.db import engine
from app.llm import obter_provider
from app.seguranca import (
    METODOS_AUDITADOS,
    ROTAS_COM_CUSTO,
    ConfiguracaoInsegura,
    exigir_admin,
    identificar_ator,
    limitador_geral,
    limitador_llm,
    registrar_requisicao,
    teto_llm,
    verificar_configuracao,
)

logger = logging.getLogger(__name__)

# A documentacao interativa e um mapa completo da superficie de ataque, com
# botao de disparo em cada rota. Util em dev, gratuito para quem sonda em
# producao.
_docs = None if settings.producao else "/docs"

app = FastAPI(
    title="FAROL v2: API",
    description="Fluxo de Atendimento, Resolucao e Orientacao em Laco: SECOEAD/EMERON",
    version="0.1.0",
    docs_url=_docs,
    redoc_url=None if settings.producao else "/redoc",
    openapi_url=None if settings.producao else "/openapi.json",
)


@app.on_event("startup")
def conferir_ambiente() -> None:
    """Ou o ambiente esta seguro quando o servico sobe, ou o servico nao sobe."""
    problemas = verificar_configuracao()
    if not problemas:
        return
    if settings.producao:
        raise ConfiguracaoInsegura(
            "FAROL nao subiu por configuracao insegura:\n  - " + "\n  - ".join(problemas)
        )
    for problema in problemas:
        logger.warning("configuracao: %s", problema)


# Ordem importa: o middleware declarado por ultimo roda primeiro. O de
# seguranca precisa ver a requisicao antes de qualquer coisa gastar recurso.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origens_web,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    # Lista fechada: `*` com credenciais habilitadas devolve qualquer
    # cabecalho que o atacante pedir.
    allow_headers=["Content-Type", "Authorization", "X-Farol-Token"],
    max_age=600,
)

if settings.hosts:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.hosts)


def _recusar(ator: str, request: Request, motivo: str, espera: str) -> JSONResponse:
    """Recusa por excesso, com registro.

    Bloqueio que nao deixa rastro e o pior tipo de bloqueio: no dia
    seguinte ninguem consegue dizer se houve abuso, de onde veio, nem se o
    limite esta calibrado. O 429 entra na trilha como qualquer outra acao.
    """
    if request.method in METODOS_AUDITADOS:
        registrar_requisicao(
            ator=ator,
            metodo=request.method,
            rota=request.url.path,
            status_code=429,
            duracao_ms=0,
            restrita=request.url.path.startswith(("/api/demo", "/api/ensaio")),
        )
    return JSONResponse({"detail": motivo}, status_code=429, headers={"Retry-After": espera})


@app.middleware("http")
async def portao(request: Request, call_next):
    """Limite por origem, teto de custo e trilha de auditoria, nesta ordem."""
    ator = identificar_ator(request)
    rota = request.url.path
    inicio = time.perf_counter()

    if not limitador_geral.permitir(ator):
        return _recusar(
            ator, request, "Muitas requisicoes. Tente de novo em um minuto.", espera="60"
        )

    # As rotas que falam com o provedor tem porteiro proprio: sao as unicas
    # em que uma requisicao a mais e dinheiro a menos.
    if rota.startswith(ROTAS_COM_CUSTO) and not limitador_llm.permitir(ator):
        logger.warning("limite de LLM atingido por %s em %s", ator, rota)
        return _recusar(
            ator, request, "Muitas mensagens seguidas. Aguarde alguns segundos.", espera="20"
        )

    resposta = await call_next(request)
    duracao_ms = int((time.perf_counter() - inicio) * 1000)

    # Cabecalhos de defesa do navegador. O front e servido pela mesma
    # origem, entao a politica pode ser restritiva sem quebrar nada.
    resposta.headers["X-Content-Type-Options"] = "nosniff"
    resposta.headers["X-Frame-Options"] = "SAMEORIGIN"
    resposta.headers["Referrer-Policy"] = "same-origin"
    resposta.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    if settings.producao:
        resposta.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

    if request.method in METODOS_AUDITADOS:
        restrita = rota.startswith(("/api/demo", "/api/ensaio"))
        registrar_requisicao(
            ator=ator,
            metodo=request.method,
            rota=rota,
            status_code=resposta.status_code,
            duracao_ms=duracao_ms,
            restrita=restrita,
        )

    return resposta


@app.exception_handler(Exception)
async def erro_interno(request: Request, erro: Exception) -> JSONResponse:
    """Erro nao tratado nunca vaza rastro de pilha para o cliente.

    Um traceback publica caminho de arquivo, versao de biblioteca e, no pior
    caso, o trecho de configuracao que causou a falha. O detalhe fica no log
    do servidor, onde a equipe alcanca e o visitante nao.
    """
    logger.exception("erro nao tratado em %s %s", request.method, request.url.path)
    return JSONResponse({"detail": "Erro interno. A equipe foi notificada."}, status_code=500)


# Todas as rotas vivem sob /api, em desenvolvimento e em producao.
# O front sempre falou com /api; ate aqui quem removia o prefixo era o
# proxy do servidor de desenvolvimento, que nao existe em producao. Com o
# prefixo no proprio backend, o caminho e o mesmo nos dois ambientes: uma
# divergencia a menos para descobrir na hora do deploy.
PREFIXO = "/api"

app.include_router(busca.router, prefix=PREFIXO)
app.include_router(atendimento.router, prefix=PREFIXO)
app.include_router(canal.router, prefix=PREFIXO)
app.include_router(fila.router, prefix=PREFIXO)
app.include_router(antecipacao.router, prefix=PREFIXO)
app.include_router(radar.router, prefix=PREFIXO)
app.include_router(governanca.router, prefix=PREFIXO)

# Superficie restrita: o Console move o relogio do mundo e reseta o banco.
# A protecao fica aqui, na inclusao, e nao rota a rota: assim uma rota nova
# no Console nasce protegida em vez de nascer esquecida.
app.include_router(demo.router, prefix=PREFIXO, dependencies=[Depends(exigir_admin)])


@app.get("/health")
@app.get("/api/health")
def health() -> dict:
    """Diz a verdade sobre o estado do sistema, inclusive quando degradado."""
    mundo_semeado = None
    try:
        with engine.connect() as conexao:
            conexao.execute(text("SELECT 1"))
            # Banco no ar mas vazio e um estado que engana: a interface abre
            # e nao mostra nada, e parece defeito de front. Melhor dizer.
            mundo_semeado = (
                conexao.execute(text("SELECT count(*) FROM participante")).scalar_one() > 0
            )
        banco = "ok"
    except Exception as erro:  # noqa: BLE001, health check nunca deve derrubar o processo
        banco = f"erro: {erro.__class__.__name__}"

    provider = obter_provider()
    orcamento = teto_llm.estado
    return {
        "servico": "farol-api",
        "banco": banco,
        "mundo_semeado": mundo_semeado,
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
        "ambiente": settings.ambiente,
        # Nenhum segredo aqui: so a contagem. Saber quanto do orcamento do
        # dia ja foi gasto e o que permite agir antes de acabar.
        "orcamento_llm": orcamento,
    }


# --------------------------------------------------------------------------
# O front, servido pelo proprio backend
# --------------------------------------------------------------------------
#
# Uma origem so, e nao duas. O front chama caminho relativo, entao nao ha
# CORS a liberar, nao ha URL de API para configurar no build e o WebSocket
# do espelho sobe na mesma origem, com o mesmo certificado. Em
# desenvolvimento esta pasta nao existe e nada disto acontece: quem serve
# continua sendo o Vite, com recarga a quente.

# .../apps/api/app/main.py -> parents[2] e .../apps
PASTA_WEB = Path(__file__).resolve().parents[2] / "web" / "dist"

if PASTA_WEB.is_dir():
    # Os arquivos com hash no nome sao imutaveis por construcao: o hash muda
    # quando o conteudo muda. Cache longo neles, nenhum no index.html, que e
    # quem aponta para os demais.
    app.mount("/assets", StaticFiles(directory=PASTA_WEB / "assets"), name="assets")

    @app.get("/{caminho:path}", include_in_schema=False)
    def spa(caminho: str) -> FileResponse:
        """Qualquer rota nao-API devolve o index: o roteamento e do navegador.

        Chega aqui so o que os routers de /api nao atenderam, porque este
        e o ultimo a ser registrado. Um arquivo real na raiz do build
        (favicon, manifest) e servido como esta; o resto e navegacao.
        """
        arquivo = (PASTA_WEB / caminho).resolve()
        if caminho and arquivo.is_file() and arquivo.is_relative_to(PASTA_WEB):
            return FileResponse(arquivo)
        return FileResponse(
            PASTA_WEB / "index.html",
            headers={"Cache-Control": "no-cache"},
        )

    logger.info("servindo o front de %s", PASTA_WEB)
