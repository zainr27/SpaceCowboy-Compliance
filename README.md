# spacebio-translator

AI-assisted translation of biotech experiments for ISS deployment.

## Setup

```bash
cp .env.example .env  # Fill in your API keys
make db-up            # Start Postgres
make migrate          # Apply migrations
make dev              # Run API at http://localhost:8000
```

## Database

Local Postgres runs in Docker via `make db-up`. The schema is managed by Alembic.

### Common commands

- `make db-up` — Start Postgres
- `make migrate` — Apply all pending migrations
- `make migration name=add_foo` — Generate a new migration from model changes
- `make db-shell` — Open a psql shell
- `make db-reset` — Drop and recreate the database (destroys all data)

### Schema overview

- `documents` — Source documents (papers, NASA guides, CASIS solicitations, etc.)
- `chunks` — Chunked, embedded slices of documents for retrieval
- `eval_examples` — Golden-set queries with ground truth for retrieval evaluation
- `eval_runs` — Historical eval results for tracking quality over time

Embeddings use Voyage AI `voyage-3-large` (1024 dimensions). Switching embedding models requires a migration.

## Development

```bash
make test    # Run unit + integration tests
make lint    # Lint and auto-fix
make type    # Type check
make check   # All of the above
```
