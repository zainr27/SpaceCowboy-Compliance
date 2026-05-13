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

**Corpus gap:** The ELV payload safety review document (NTRS 20130011541) is not yet in the corpus. The `safety_eclss_flammability_01` eval example currently targets ECLSS payload safety content as a stand-in. Add the ELV doc via `make ingest` when available and add a dedicated `safety_elv_review_01` example to cover that intent properly.

## Agents

```bash
make hw-agent preset=cell_culture          # Hardware compatibility analysis
make hw-agent preset=plant_growth
make hw-agent preset=protein_crystallization
make hw-agent preset=cell_culture top_n=12  # Override retrieval depth
```

The hardware agent uses multi-query retrieval: each protocol is decomposed into 2–3 orthogonal queries (capability, environmental, operational), run in parallel, merged by best-score-per-chunk, and deduped before the LLM reasoning pass. This pattern generalises to all sub-agents via `_decompose_query()`.

### Hardware agent: known corpus gap

The `cell_culture` preset scores low confidence (0.30) because the corpus lacks hardware specs that address (a) automated media exchange and (b) fine-grained CO2 control. MVP's flysheet mentions 5% CO2 but not the precise control range; ADSEP doesn't address CO2 at all.

Fix: ingest specs for BioServe SABL, Space Tango cell culture cassettes, or any incubator-class ISS hardware. Address before the orchestrator layer — cell culture is a common protocol category and the gap will be visible in synthesised output.

## Development

```bash
make test    # Run unit + integration tests
make lint    # Lint and auto-fix
make type    # Type check
make check   # All of the above
```
