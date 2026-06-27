# SpaceCowboy Compliance

**Compliance analysis for biotech experiments destined for low-Earth orbit.**

You describe a biological protocol. Spacebio Translator runs it through five parallel AI agents — each an expert in a different dimension of spaceflight readiness — and returns a single structured report: what hardware fits, what microgravity adaptations are required, what the safety classification is, which mission platforms can carry it, and what regulatory frameworks apply. The whole pipeline runs in under 20 seconds.

---

## What it does

Getting a biology experiment to the ISS means clearing five independent gates before the payload safety review board will even look at it. Most researchers treat each gate as a separate manual exercise. This tool runs them in parallel against a curated corpus of NASA documents, hardware flysheets, ISS research guides, and regulatory frameworks.

The five agents:

| Agent | Question answered |
|---|---|
| **Hardware** | Which ISS research hardware fits this protocol, and what gaps exist? |
| **Microgravity** | What assumptions in the earthbound protocol break in microgravity, and how must it change? |
| **Safety** | What is the biosafety classification, and what hazards require NASA review? |
| **Mission** | Which facility, ascent vehicle, and resource budget (cold stowage, crew time) does this need? |
| **Regulatory** | Which frameworks — NASA payload safety, FDA, ITAR, CASIS, GINA — apply, and at what level? |

Every finding is grounded in retrieved source chunks. Citations are deduplicated across agents and ranked by relevance — you can see exactly which document each claim came from.

---

## Results on three representative protocols

All three runs: **5/5 agents succeeded**, 31 unit tests passing.

### Plant growth (Arabidopsis, 30 days)
```
Runtime: 14s   Overall confidence: 0.66

  Hardware:      0.60  ████████████░░░░░░░░
  Microgravity:  0.80  ████████████████░░░░
  Safety:        0.60  ████████████░░░░░░░░
  Mission:       0.70  ██████████████░░░░░░
  Regulatory:    0.60  ████████████░░░░░░░░

Hardware:     Redwire MVP, fit_score=0.80, 1 gap (water delivery unspecified in corpus)
Microgravity: 2 modifications, 1 critical (fluid handling) — backed by plant water management paper
Safety:       BSL-1, 2 hazards (RNAlater chemical, water delivery), 2 NASA review milestones
Mission:      TangoLab / SpaceX Dragon / cold stowage required
Regulatory:   NASA_payload_safety = required, CASIS_ISS_National_Lab = likely_applicable
Citations:    14 unique sources across all 5 agents
Open questions: 6 (RNAlater containment, water delivery standards, upmass, timeline, CASIS terms, ITAR trigger)
```

### Cell culture (continuous mammalian culture)
```
Runtime: 8.5s   Overall confidence: 0.62

Hardware:     MVP fit_score=0.80, 2 gaps flagged (CO2 control, media exchange) — known corpus gap
Mission:      TangoLab / Dragon
Cross-agent:  corpus_gap insight — CASIS open questions surfaced by both regulatory and mission agents
```

### Protein crystallization (batch, microgravity-assisted)
```
Runtime: 17.5s   Overall confidence: 0.56

Hardware:     ADSEP fit_score=0.70 — correctly chosen over TangoLab for batch crystallization
Safety:       BSL-1, 1 hazard
Mission:      TangoLab, no cold stowage required
Microgravity: 2 modifications, 0 critical — correct, crystal quality improves in microgravity
```

---

## How it works

```
Protocol description (text)
        │
        ▼
  ParallelExecutor  ──── asyncio.gather ────────────────────────────────────┐
        │                                                                    │
        ├── HardwareAgent      (capability + environment + operational queries)
        ├── MicrogravityAgent  (physics + biology + precedent queries)
        ├── SafetyAgent        (biosafety + hazard + containment queries)
        ├── MissionAgent       (facility + logistics + resource queries)
        └── RegulatoryAgent    (framework + compliance + IP queries)
                                                                             │
        ◄────────────────────────────────────────────────────────────────────┘
        │
        ▼
  RuleBasedSynthesizer
        ├── Deduplicate citations by chunk_id, rank by best relevance score
        ├── Average confidence across successful agents
        ├── Detect cross-agent insights (BSL vs containment tension, compound risk, corpus gaps)
        ├── Aggregate open questions, deduplicate
        └── Single LLM call → ExecutiveSummary (headline, biosafety, facility, pathway, regulatory floor)
        │
        ▼
  OrchestratorReport  (structured JSON or formatted terminal output)
```

Each agent uses **multi-query retrieval**: the protocol is decomposed into 2–3 orthogonal queries, run in parallel against the knowledge base, merged by best-score-per-chunk, diversified across documents, and reranked before the LLM reasoning pass.

The knowledge base uses **Voyage AI `voyage-3-large`** dense embeddings + PostgreSQL `tsvector` sparse search, fused via Reciprocal Rank Fusion, with **Cohere `rerank-english-v3.0`** reranking.

---

## Setup

**Prerequisites:** Docker, Python 3.11+, `uv`

```bash
cp .env.example .env      # Add API keys: OPENAI_API_KEY, COHERE_API_KEY, VOYAGE_API_KEY
make db-up                # Start Postgres + pgvector in Docker
make migrate              # Apply schema migrations
make seed                 # Ingest every PDF under corpus/ into the KB
make dev                  # API at http://localhost:8000
```

> **The knowledge base starts empty.** Corpus PDFs are gitignored
> (`.gitignore`: `corpus/**/*.pdf`), so a fresh clone has no documents and the
> KB is empty until you ingest. Drop PDFs into the `corpus/` subdirectories
> (e.g. `corpus/nasa_payload_guides/`, `corpus/hardware_specs/`,
> `corpus/papers/`) and run `make seed`. Without this step every agent runs
> against an empty KB and the headline results below are not reproducible.
> `make seed` skips already-ingested documents (checksum dedup), so it is safe
> to re-run.

**Required API keys:**
- `OPENAI_API_KEY` — LLM reasoning (gpt-4o)
- `COHERE_API_KEY` — Reranking (rerank-english-v3.0), production key recommended
- `VOYAGE_API_KEY` — Dense embeddings (voyage-3-large)

---

## Running the orchestrator

```bash
make orchestrate preset=plant_growth
make orchestrate preset=cell_culture
make orchestrate preset=protein_crystallization

# Raw JSON output
SSL_CERT_FILE=$(uv run python -c "import certifi; print(certifi.where())") \
PYTHONPATH=. uv run python scripts/orchestrate.py --preset plant_growth --json
```

### Running individual agents

```bash
make hw-agent       preset=plant_growth      # Hardware compatibility
make mg-agent       preset=plant_growth      # Microgravity adaptation
make safety-agent   preset=cell_culture      # Safety screening
make mission-agent  preset=plant_growth      # Mission integration
make reg-agent      preset=cell_culture      # Regulatory pathway
```

### Ingesting documents

Bulk-ingest everything under `corpus/` (skips already-ingested docs):

```bash
make seed
```

Ingest a single PDF:

```bash
make ingest path=path/to/doc.pdf title="Document Title" type=hardware_spec url=https://...
```

Source types: `hardware_spec`, `safety_guide`, `research_paper`, `regulatory_doc`, `mission_guide`, `iss_annual_report`

---

## Knowledge base

The corpus is NASA documents, ISS hardware flysheets, research papers, and regulatory references. The system is only as good as what's been ingested.

**Current corpus coverage:**
- ISS hardware: Redwire MVP, ADSEP, Space Tango CubeLab ICD, TangoLab
- Biology: plant science papers, microgravity cell culture literature
- Safety: NASA payload safety review guides, PSWG documentation
- Mission: ISS annual reports, CASIS solicitation guides
- Regulatory: export control, biosafety, IP governance references

**Known gap:** No BioServe SABL or Space Tango cell culture cassette specs in the corpus. The cell culture hardware agent correctly surfaces this as a gap (CO2 control, media exchange unspecified). Fix: ingest SABL spec when available.

---

## Development

```bash
make test    # Unit tests (excludes slow integration tests)
make lint    # Ruff lint + format
make type    # mypy
make check   # All of the above

make eval       # Retrieval eval suite (hits Cohere API)
make eval-fast  # Evals without reranking
```

**Test markers:**
- Default (`make test`): unit tests only, no external API calls
- `pytest -m slow`: integration tests, requires live DB + API keys
- `pytest -m evals`: retrieval quality evals

---

## Database

```bash
make db-up        # Start Postgres
make migrate      # Apply migrations
make migration name=add_foo   # Generate migration from model changes
make db-shell     # psql shell
make db-reset     # Drop and recreate (destroys all data)
```

Schema: `documents`, `chunks` (with pgvector embeddings), `eval_examples`, `eval_runs`.
