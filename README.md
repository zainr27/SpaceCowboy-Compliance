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

Two sub-agents are operational. Both use multi-query retrieval: each protocol is decomposed into 2–3 orthogonal queries, run in parallel via `KnowledgeBase.search_many()`, merged by best-score-per-chunk, and deduped before the LLM reasoning pass. The pattern is in `packages/agents/base.py:retrieve_multi_query()` and each agent overrides `_decompose_query()`.

### Hardware Agent — ISS hardware compatibility

```bash
make hw-agent preset=cell_culture
make hw-agent preset=plant_growth
make hw-agent preset=protein_crystallization
```

Query facets: capability (what kind of hardware), environmental (temp/CO2/biosafety), operational (imaging/media exchange/sample return). Output: recommended hardware with fit scores, gaps with severity, resolved citations.

Confidence as of last run: `protein_crystallization` 0.60, `plant_growth` 0.60, `cell_culture` 0.30.

**Known corpus gap:** `cell_culture` scores low because no hardware specs address automated media exchange or fine-grained CO2 control. Fix: ingest BioServe SABL or Space Tango cell culture cassette specs before building the orchestrator.

### Microgravity Adaptation Agent — protocol modifications for spaceflight

```bash
make mg-agent preset=plant_growth
make mg-agent preset=cell_culture
make mg-agent preset=protein_crystallization
```

Query facets: physics (fluid/convection/diffusion), biology (organism-specific microgravity response), precedent (prior spaceflight experiments). Output: protocol modifications (earthbound assumption → microgravity reality → recommended change, each with severity), expected behaviors, research precedents — all grounded in retrieved sources.

Confidence as of last run: `plant_growth` 0.80 (plant corpus is strong), `cell_culture` 0.70, `protein_crystallization` 0.70.

## Development

```bash
make test    # Run unit + integration tests
make lint    # Lint and auto-fix
make type    # Type check
make check   # All of the above
```
