# Imagem unica: o front construido vai dentro da imagem da API, que o serve.
# Um servico para hospedar, uma origem, um certificado.

# --------------------------------------------------------------------------
# 1. Front
# --------------------------------------------------------------------------
FROM node:22-alpine AS web

WORKDIR /web
# Copiar so o manifesto antes do codigo faz o npm ci ficar em cache entre
# builds: dependencia muda raramente, codigo muda a cada commit.
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci

COPY apps/web/ ./
RUN npm run build

# --------------------------------------------------------------------------
# 2. API
# --------------------------------------------------------------------------
FROM python:3.12-slim AS api

# PYTHONDONTWRITEBYTECODE: o .pyc nao serve de nada em container efemero.
# PYTHONUNBUFFERED: sem isto o log fica preso no buffer e o painel da
# hospedagem mostra uma tela vazia enquanto o servico ja esta falando.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY apps/api/pyproject.toml ./apps/api/
COPY apps/api/app ./apps/api/app
COPY apps/api/alembic ./apps/api/alembic
COPY apps/api/alembic.ini ./apps/api/
RUN pip install --no-cache-dir ./apps/api

COPY --from=web /web/dist ./apps/web/dist

# Usuario sem privilegio: se um dia houver execucao arbitraria dentro do
# container, que ela aconteca sem poder escrever no proprio codigo.
RUN useradd --create-home --uid 10001 farol && chown -R farol:farol /app
USER farol

ENV AMBIENTE=producao
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"

WORKDIR /app/apps/api
# Sem --reload e com proxy-headers: atras do proxy da hospedagem, e o
# X-Forwarded-For que diz de onde veio a requisicao. Sem isto, o limite por
# origem contaria todo mundo como o mesmo ator, o do proxy.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--forwarded-allow-ips", "*"]
