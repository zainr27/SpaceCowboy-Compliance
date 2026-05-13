.PHONY: help install dev test eval eval-fast lint type format db-up db-down db-shell db-reset clean ingest search agent-search hw-agent mg-agent safety-agent

help:
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-15s %s\n", $$1, $$2}'

install: ## Install dependencies
	uv sync

dev: ## Run API in dev mode
	uv run uvicorn apps.api.main:app --reload --port 8000

test: ## Run unit tests (excludes evals and slow)
	SSL_CERT_FILE=$$(uv run python -c "import certifi; print(certifi.where())") \
	PYTHONPATH=. uv run pytest -m "not evals and not slow" -v

eval: ## Run the retrieval eval suite
	SSL_CERT_FILE=$$(uv run python -c "import certifi; print(certifi.where())") \
	PYTHONPATH=. uv run python scripts/run_evals.py

eval-fast: ## Run evals without reranking (faster, no Cohere calls)
	PYTHONPATH=. uv run python scripts/run_evals.py --no-rerank

lint: ## Lint and auto-fix
	uv run ruff check --fix .
	uv run ruff format .

type: ## Type check
	uv run mypy packages apps

format: ## Format only
	uv run ruff format .

check: lint type test ## Run all checks

db-up: ## Start postgres
	docker compose up -d
	@echo "Waiting for postgres..."
	@until docker compose exec -T postgres pg_isready -U postgres > /dev/null 2>&1; do sleep 1; done
	@echo "Postgres ready"

db-down: ## Stop postgres
	docker compose down

db-shell: ## Open psql shell
	docker compose exec postgres psql -U postgres -d spacebio

db-reset: ## Drop and recreate database
	docker compose down -v
	docker compose up -d
	@until docker compose exec -T postgres pg_isready -U postgres > /dev/null 2>&1; do sleep 1; done
	uv run alembic upgrade head

migrate: ## Run migrations
	uv run alembic upgrade head

migration: ## Create new migration (usage: make migration name=add_foo)
	uv run alembic revision --autogenerate -m "$(name)"

ingest: ## Ingest a PDF. Usage: make ingest path=... title=... type=... url=...
	SSL_CERT_FILE=$$(uv run python -c "import certifi; print(certifi.where())") \
	PYTHONPATH=. uv run python scripts/ingest_pdf.py \
		--path "$(path)" \
		--source-type "$(type)" \
		--title "$(title)" \
		--source-url "$(url)"

search: ## Search the knowledge base. Usage: make search q="your query"
	PYTHONPATH=. uv run python scripts/retrieve.py "$(q)"

agent-search: ## Profile-scoped KB search. Usage: make agent-search profile=hardware q="..."
	SSL_CERT_FILE=$$(uv run python -c "import certifi; print(certifi.where())") \
	PYTHONPATH=. uv run python scripts/agent_search.py "$(profile)" "$(q)"

hw-agent: ## Run hardware compatibility agent. Usage: make hw-agent preset=cell_culture
	SSL_CERT_FILE=$$(uv run python -c "import certifi; print(certifi.where())") \
	PYTHONPATH=. uv run python scripts/hardware_agent.py --preset "$(preset)"

mg-agent: ## Run microgravity adaptation agent. Usage: make mg-agent preset=plant_growth
	SSL_CERT_FILE=$$(uv run python -c "import certifi; print(certifi.where())") \
	PYTHONPATH=. uv run python scripts/microgravity_agent.py --preset "$(preset)"

safety-agent: ## Run safety screening agent. Usage: make safety-agent preset=cell_culture
	SSL_CERT_FILE=$$(uv run python -c "import certifi; print(certifi.where())") \
	PYTHONPATH=. uv run python scripts/safety_agent.py --preset "$(preset)"

clean: ## Clean caches
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
