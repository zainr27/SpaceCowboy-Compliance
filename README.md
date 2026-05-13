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

## Evals

```bash
make eval       # Full eval suite with Cohere reranking (~10s, hits Cohere API)
make eval-fast  # Eval without reranking (no Cohere calls, faster)
```

Results are persisted to the `eval_runs` table for trend tracking.

### Known limitations of the current eval set

**TODO: The eval set is currently lexically easy.** Coverage scores trend high (0.9+) because expected keywords are exact domain jargon that appears verbatim in a single document. Before relying on these numbers as a regression signal, add 5–10 paraphrased queries that test semantic retrieval rather than keyword matching — e.g., ask about "air mixture oxygen fraction management" instead of "ECLSS pressure" to force the system to match on meaning rather than token overlap.

**Corpus gap:** The ELV payload safety review document (NTRS 20130011541) is not yet in the corpus. The `safety_payload_review_01` eval example currently targets ECLSS safety content as a stand-in. Add the ELV doc via `make ingest` when available to restore the original intent of that example.

## Development

```bash
make test    # Run unit + integration tests
make lint    # Lint and auto-fix
make type    # Type check
make check   # All of the above
```
