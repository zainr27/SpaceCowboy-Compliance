.PHONY: help install dev test eval lint type format db-up db-down db-shell db-reset clean ingest

help:
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-15s %s\n", $$1, $$2}'

install: ## Install dependencies
	uv sync

dev: ## Run API in dev mode
	uv run uvicorn apps.api.main:app --reload --port 8000

test: ## Run unit tests (excludes evals)
	uv run pytest -m "not evals" -v

eval: ## Run eval suite
	uv run pytest -m "evals" -v

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

clean: ## Clean caches
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
