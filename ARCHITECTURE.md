# Architecture — Financial Intelligence Platform (AMMC)

## Overview

A hybrid RAG system that answers questions about Moroccan listed companies by combining:
- **PostgreSQL** — structured financial facts (numbers, ratios, statements)
- **ChromaDB** — semantic document search over annual report text
- **LLM (Groq/llama-3.3-70b)** — answer synthesis

---

## Directory Structure

```
chatbot-ammc/
├── ammc_report_scraper/       # AMMC.ma PDF scraper (unchanged)
├── api/
│   └── main.py                # FastAPI: existing + new /api/companies, /api/search endpoints
├── db/
│   ├── __init__.py
│   ├── models.py              # SQLAlchemy 2.0 models (11 tables)
│   └── session.py             # Engine, SessionLocal, get_db(), check_connection()
├── extraction/
│   ├── confidence.py          # Weighted confidence scoring
│   ├── financial_extractor.py # Main extraction pipeline
│   ├── normalizer.py          # French number parsing, unit detection
│   ├── ocr_detector.py        # Detect image-only PDFs
│   ├── table_analyzer.py      # pdfplumber table → metric cells
│   ├── validator.py           # Balance sheet / income stmt validation
│   └── vocabulary.py          # French/English metric alias mapping
├── retrieval/
│   ├── router.py              # Classify question as SQL / VECTOR / HYBRID
│   ├── sql_retriever.py       # Read-only parameterized SQL queries
│   ├── vector_retriever.py    # Thin wrapper around ChromaDB (chat.retrieve)
│   └── hybrid_retriever.py    # Orchestrates router + SQL + vector
├── scripts/
│   ├── populate_db.py         # Seed companies + reports from scraper manifest
│   ├── extract_financial_data.py  # Run extraction on all PDFs → PostgreSQL
│   ├── validate_extraction.py # Post-extraction validation report
│   └── data_quality_report.py # Per-company quality summary
├── tests/
│   ├── test_normalization.py  # French number + unit parsing (unit tests)
│   ├── test_validation.py     # Financial validation rules (unit tests)
│   ├── test_router.py         # Query routing classification (unit tests)
│   └── test_sql_retriever.py  # SQL queries (integration, skipped if no DB)
├── alembic/                   # Database migrations
│   └── versions/001_initial_schema.py
├── build_index.py             # ChromaDB indexing pipeline (unchanged)
├── chat.py                    # LLM chat + ChromaDB retrieve (unchanged)
├── config.py                  # All config constants + env vars
├── docker-compose.yml         # PostgreSQL 16-alpine
└── ingest_scraped.py          # Bridge: scraper → data/pdfs/ + index
```

---

## Data Flow

### Ingestion
```
AMMC.ma
  └─► ammc_report_scraper/  (download PDFs)
         └─► reports_manifest.csv
                └─► ingest_scraped.py
                       ├─► data/pdfs/{company}_{year}.pdf  (renamed copies)
                       └─► build_index.py  ──► ChromaDB (.chroma/)

scripts/populate_db.py  ──► PostgreSQL: companies + reports (pending)
scripts/extract_financial_data.py  ──► PostgreSQL: metrics + statements
```

### Query
```
User question
  └─► retrieval/router.py  (classify: SQL / VECTOR / HYBRID)
         ├─► [SQL]    sql_retriever.py  ──► PostgreSQL financial_metrics
         ├─► [VECTOR] vector_retriever.py ──► ChromaDB chunks
         └─► [HYBRID] both branches merged
                └─► HybridResult.build_context()
                       └─► chat.py answer()  ──► LLM  ──► response
```

---

## Database Schema (11 tables)

| Table | Purpose |
|---|---|
| `companies` | Company master (name, sector, ammc_id) |
| `reports` | One row per PDF (path, hash, extraction_status) |
| `report_sections` | Named sections with page ranges |
| `financial_metrics` | All extracted metrics with confidence + provenance |
| `income_statements` | Structured income statement fields |
| `balance_sheets` | Structured balance sheet with validation flag |
| `cash_flows` | Cash flow statement fields |
| `financial_ratios` | Reported or calculated ratios |
| `shareholders` | Ownership structure |
| `extraction_jobs` | Per-report extraction run metadata |
| `extraction_errors` | Error log with stack traces |

Key constraints:
- `UNIQUE(company_id, year, report_type)` on `reports`
- `UNIQUE(report_id, normalized_metric_name, year, statement_type)` on `financial_metrics`
- All monetary values stored as `NUMERIC(20,4)` in MAD

---

## Query Routing

The router (`retrieval/router.py`) uses deterministic keyword matching — no LLM call:

| Signal | Route |
|---|---|
| Financial metric keywords (résultat net, EBITDA, total actif…) | **SQL** |
| Narrative keywords (stratégie, risques, gouvernance, RSE…) | **VECTOR** |
| Causal keywords (pourquoi, impact, facteur…) + any other signal | **HYBRID** |
| No clear signal | **VECTOR** (safe default) |

---

## Setup

```bash
# 1. Start PostgreSQL
docker compose up -d

# 2. Create tables
alembic upgrade head

# 3. Copy .env
cp .env.example .env  # set GROQ_API_KEY

# 4. Populate DB from scraper manifest
python scripts/populate_db.py

# 5. Run financial extraction
python scripts/extract_financial_data.py --limit 20  # test with 20 first

# 6. Validate
python scripts/validate_extraction.py
python scripts/data_quality_report.py

# 7. Run tests
python -m pytest tests/ -v

# 8. Start API
uvicorn api.main:app --reload
```

---

## Design Principles

- **Correctness > speed**: validation flags bad data instead of silently storing it
- **Traceability**: every metric stores source_page, source_text, confidence, extraction_method
- **No hallucination**: SQL returns NULL when data absent; LLM told explicitly to say "données non disponibles"
- **Idempotency**: file_hash + unique constraints prevent duplicate extraction runs
- **Graceful degradation**: if PostgreSQL unreachable, API falls back to ChromaDB-only mode
- **French financial vocabulary**: normalizer handles "1 245,50", "(125)", MMAD/MDH/milliards
