.PHONY: setup db dev api web migrate revision seed reset test lint

VENV := .venv
PY   := $(VENV)/bin/python
PIP  := $(VENV)/bin/pip

setup: ## Instala tudo do zero
	python3 -m venv $(VENV)
	$(PIP) install -q -e "apps/api[dev]"
	cd apps/web && npm install
	@test -f .env || cp .env.example .env
	@echo "Pronto. Defina ANTHROPIC_API_KEY no .env e rode: make dev"

db: ## Sobe o Postgres com pgvector
	docker compose -f infra/docker-compose.yml up -d
	@until docker exec farol-db pg_isready -U farol -d farol >/dev/null 2>&1; do sleep 1; done
	@echo "Banco no ar em localhost:5434"

migrate: db ## Aplica as migrations
	cd apps/api && ../../$(VENV)/bin/alembic upgrade head

revision: ## Gera migration a partir dos models: make revision m="descricao"
	cd apps/api && ../../$(VENV)/bin/alembic revision --autogenerate -m "$(m)"

seed: migrate ## Popula o banco com o mundo ficticio
	cd apps/api && ../../$(VENV)/bin/python -m app.seed

api: ## Sobe so a API
	cd apps/api && ../../$(VENV)/bin/uvicorn app.main:app --reload --port 8000

web: ## Sobe so o front
	cd apps/web && npm run dev

dev: migrate ## Sobe banco, API e front juntos
	@$(MAKE) -j2 api web

test:
	cd apps/api && ../../$(VENV)/bin/pytest

lint:
	$(VENV)/bin/ruff check apps/api
	cd apps/web && npx tsc -b

reset: ## Apaga o banco, recria e repopula
	docker compose -f infra/docker-compose.yml down -v
	@$(MAKE) seed
