# Policy Events ETL — Solution Documentation

## Executive summary

This solution implements a **batch ETL pipeline** in Python that ingests JSON Lines policy event files, cleans and validates them, builds a **normalized dimensional model**, and loads queryable outputs to **Parquet** and **SQLite**. Example analyst queries from the brief are implemented and runnable via CLI.

---

## Scope decisions and assumptions

The brief allows narrowing scope. Deliberate choices:

| Decision | Rationale |
|----------|-----------|
| **Batch-only** (not streaming) | Source data is static JSON part files; streaming adds complexity without benefit for this dataset. |
| **Local execution** (no cloud IaC) | Maximises portability for reviewers; production scaling is documented, not deployed. |
| **SQLite + Parquet warehouse** | Lightweight, zero-infra query layer for analysts; Parquet enables future migration to S3/BigQuery/Snowflake. |
| **Type-1 dimensions** | No historical tracking of product/brand changes per policy in source; SCD2 would need explicit effective dates. |
| **Active policy = latest lifecycle event** | `purchase` / `renewal` → active; `cancellation` → inactive; `claim` does not change lifecycle status. |
| **Quarantine invalid rows** | Bad data is isolated rather than failing the entire batch (resilience). |

**Out of scope (documented for production):** real-time ingestion, orchestration (Airflow/Dagster), IAM/secrets, PII masking, data catalog, and full CI/CD to cloud.

---

## How to run (evaluation team)

### Prerequisites

- Python 3.10+
- pip

### Setup

```bash
cd "Data engineering take home test"
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Run ETL + example queries

```bash
python main.py --run-queries
```

Outputs land in `output/`:

```
output/
  staging/           # raw extract checkpoint per run
  warehouse/         # Parquet dimensions, facts, marts
    policy_analytics.db
  quarantine/        # rejected rows (if any)
```

### Run unit tests

```bash
pytest -v
```

### Custom paths

```bash
python main.py --input-dir ./policy_data --output-dir ./output --run-queries
```

---

## Solution architecture

```
policy_data/*.json (JSONL)
        │
        ▼
   [Extract]  ──► staging/raw_events_{run_id}.parquet
        │
        ▼
   [Transform]
     • Parse policy_type string → product_type, brand
     • Validate & quarantine bad rows
     • Build dimensions + fact + marts
        │
        ▼
   [Load]  ──► Parquet warehouse + SQLite (indexed)
        │
        ▼
   [Analytics]  example SQL for analyst questions
```

### Data model

**Dimensions (reduced redundancy):**

- `dim_customer` — one row per `customer_id`
- `dim_product` — distinct `(product_type, brand)`
- `dim_region` — distinct regions
- `dim_policy` — one row per `policy_id` with current attributes

**Fact:**

- `fact_policy_events` — event grain; surrogate keys to dimensions

**Marts (query performance):**

- `mart_policy_status` — current active/inactive per policy (answers “active customers”)
- `mart_renewals_daily` — pre-aggregated renewal counts and median premium by day and product type

### Example analyst queries

Implemented in `policy_etl/analytics.py`:

1. **Active customers:** `COUNT(DISTINCT customer_sk) FROM mart_policy_status WHERE status = 'active'`
2. **Renewals in 2024 by policy type:** filter `fact_policy_events` where `event_type = 'renewal'` and year 2024
3. **Median auto renewal price by day:** read from `mart_renewals_daily` where `product_type = 'auto'`

---

## Data quality handling

- Missing required fields → quarantine
- Invalid `event_type` → quarantine
- `coverage_amount` ≤ -1e9 (overflow sentinel) → quarantine
- Unparseable timestamps → quarantine
- Optional `premium_amount` retained as NULL (e.g. some renewal rows)

Quarantined rows are written to `output/quarantine/quarantined_events.parquet` for inspection and replay.

---

## Project layout

```
policy_etl/
  config.py       # constants and paths
  extract.py      # JSONL read
  parsers.py      # policy_type parsing
  transform.py    # validation, model build
  load.py         # Parquet + SQLite
  pipeline.py     # orchestration
  analytics.py    # sample queries
main.py           # CLI
tests/            # unit & integration tests
ETL_Presentation.pptx   # design deep-dive (greenfield, prod, scale)
```

---

## Production roadmap (summary)

See **PRESENTATION.md** for full detail on greenfield ETL, testing strategy, failure recovery, scaling, and data modelling.

High-level next steps:

1. Orchestrate with Airflow/Dagster; idempotent runs keyed by `run_id`
2. Land raw data in object storage (S3/GCS); process with Spark or dbt
3. Replace SQLite with warehouse (Snowflake/BigQuery/Redshift)
4. Add Great Expectations/dbt tests, monitoring, and alerting on quarantine volume
5. Secrets, network policies, and audit logging before production cutover
