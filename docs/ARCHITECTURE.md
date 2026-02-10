# System Architecture

**Last Updated:** February 10, 2026

This document details the architecture of the TokyoBeta Data Consolidation pipeline, including design decisions, component interactions, and optimization strategies.

---

## 📚 Table of Contents
1. [Pipeline Overview](#pipeline-overview)
2. [Architecture Decisions](#architecture-decisions)
3. [Component Details](#component-details)
4. [Data Layer Dependencies](#data-layer-dependencies)
5. [Optimizations](#optimizations)

---

## Pipeline Overview

The system follows a standard ELT (Extract, Load, Transform) pattern using AWS Glue and dbt.

```
EC2 Cron (5:30 AM JST)
    ↓ Generates SQL dump
S3 Bucket (jram-gghouse/dumps/)
    ↓ Stores gghouse_YYYYMMDD.sql
EventBridge Schedule (7:00 AM JST)
    ↓ Triggers daily ETL
Glue: staging_loader
    ↓ Loads dump → staging schema
Glue: silver_transformer (DEPENDS ON staging_loader)
    ↓ Runs dbt silver models (cleaning, deduplication)
Glue: gold_transformer (DEPENDS ON silver_transformer)
    ↓ Runs dbt gold models (aggregation)
QuickSight (8:00 AM JST)
    ↓ SPICE refresh
Dashboard
```

### Job Dependencies (CRITICAL)

1. **staging_loader** (5-10 min)
   - Loads SQL dump from S3 → staging schema
   - Creates backups before loading
   - Tables: `staging.movings`, `staging.tenants`, `staging.rooms`, etc.

2. **silver_transformer** (15-20 min) - **MUST wait for staging_loader**
   - Runs dbt silver models
   - Transforms staging → silver
   - Tables: `silver.int_contracts`, `silver.tokyo_beta_tenant_room_info`, etc.

3. **gold_transformer** (2-5 min) - **MUST wait for silver_transformer**
   - Runs dbt gold models
   - Aggregates silver → gold
   - Tables: `gold.daily_activity_summary`, `gold.new_contracts`, etc.

---

## Architecture Decisions

### ETL Framework Selection: AWS Glue + dbt

**Decision:** We chose **AWS Glue + dbt** over Lambda-only or Step Functions approaches.

**Rationale:**
1. **TDD Compliance**: dbt has a built-in test framework (`dbt test`) which satisfies our strict TDD requirement.
2. **Data Quality**: Glue Data Quality rules validate data before loading.
3. **Scalability**: Glue handles large dumps (900MB+) better than Lambda (15-min timeout risk).
4. **Enterprise Readiness**: Provides lineage tracking, schema evolution, and is future-proof for streaming (Kinesis).

**Trade-offs:**
- **Cost**: Higher than Lambda-only (~$60-80/month vs ~$5/month), but acceptable for enterprise reliability.
- **Complexity**: More components, but better separation of concerns.

---

## Component Details

### 1. Dump Generation (Extract)
- **Source**: Nazca RDS (MySQL)
- **Method**: `mysqldump` via cron on EC2 instance `i-00523f387117d497b`
- **Output**: Compressed SQL file in S3 (`s3://jram-gghouse/dumps/`)
- **Frequency**: Daily at 5:30 AM JST

### 2. Staging Loader (Load)
- **Service**: AWS Glue (Python Shell)
- **Script**: `glue/scripts/staging_loader.py`
- **Function**:
  - Downloads latest dump from S3
  - Loads data into Aurora `staging` schema
  - Performs "Snapshot Loading" (incremental load of daily snapshots)
  - Triggers `silver_transformer` upon success

### 3. Transformations (Transform)
- **Service**: AWS Glue (Python Shell) running dbt Core
- **Scripts**: `glue/scripts/silver_transformer.py`, `glue/scripts/gold_transformer.py`
- **Silver Layer**: Cleaning, deduplication, standardization (e.g., `silver.stg_movings`)
- **Gold Layer**: Business logic, aggregation, metrics (e.g., `gold.daily_activity_summary`)

### 4. BI Layer (Consume)
- **Service**: AWS QuickSight
- **Source**: Aurora `gold` tables
- **Refresh**: Daily SPICE refresh at 8:00 AM JST

---

## Data Layer Dependencies

### Staging Layer (Source of Truth)
Raw data loaded directly from SQL dumps.
- `staging.movings`
- `staging.tenants`
- `staging.rooms`
- `staging.inquiries`
- `staging.apartments`

### Silver Layer (Cleaned & Enriched)
- `silver.stg_movings` ← `staging.movings` (cleaning)
- `silver.stg_tenants` ← `staging.tenants` (cleaning, LLM enrichment)
- `silver.int_contracts` ← `staging.movings` + `tenants` (join)
- `silver.tokyo_beta_tenant_room_info` ← `staging.movings` + `tenants` + `rooms` + `apartments`

### Gold Layer (Business Metrics)
- `gold.daily_activity_summary` ← `silver.int_contracts` (aggregation)
- `gold.new_contracts` ← `silver.int_contracts` (filtering)
- `gold.moveouts` ← `silver.int_contracts` (status-based)
- `gold.moveout_notices` ← `silver.int_contracts` (24-month window)

---

## Optimizations

### Snapshot Loading Optimization (Feb 2026)

**Problem:** The ETL was reloading ALL 261 historical snapshots (10.3M rows) every day, taking ~8 minutes and wasting compute.

**Solution:** Implemented incremental loading.
- **Logic:** Check existing snapshot dates in DB → Only load NEW snapshots from S3.
- **Impact:**
  - **Rows loaded daily:** 10.3M → ~40K (99.6% reduction)
  - **Load time:** ~8 min → ~10 sec (98% faster)
  - **Total ETL time:** Reduced by ~30 minutes

**Code Implementation:**
```python
# Check what's already loaded
existing_dates = get_existing_snapshots_from_db()

# Only load NEW snapshots
new_snapshots = [s for s in all_snapshots if s not in existing_dates]

for csv in new_snapshots:  # Usually just 1 file (today)
    load_snapshot(csv)
```

### Future Optimizations
1. **dbt Incremental Models**: Convert large tables to incremental materialization.
2. **Parallel Processing**: Use Glue DPU workers for parallel SQL execution.
3. **Snapshot Export**: Use `SELECT INTO OUTFILE S3` for faster exports.
