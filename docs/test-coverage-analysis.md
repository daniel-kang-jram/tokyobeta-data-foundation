# Test Coverage Analysis

This document summarises the current state of test coverage across the codebase and proposes concrete areas where we should invest in additional tests.

---

## Current Coverage Landscape

| Layer | Source file(s) | Test file(s) | Estimated coverage |
|---|---|---|---|
| Staging ETL | `glue/scripts/daily_etl.py` (3 763 lines) | `glue/tests/test_daily_etl.py` (73 tests) | **Good** – core parsing, manifest, archive, credential, dbt-run paths all exercised |
| Staging loader | `glue/scripts/staging_loader.py` (617 lines) | `glue/tests/test_staging_loader.py` | **Good** – all public functions have unit tests |
| Silver transformer | `glue/scripts/silver_transformer.py` (615 lines) | `glue/tests/test_silver_transformer.py` | **Partial** – `TestMainWorkflow` contains three placeholder `pass` stubs |
| Gold transformer | `glue/scripts/gold_transformer.py` (763 lines) | `glue/tests/test_gold_transformer.py` (154 lines) | **Low** – only 3 of 12 functions have tests; `compute_occupancy_kpis` (180 lines) is untested |
| Occupancy KPI updater | `glue/scripts/occupancy_kpi_updater.py` (320 lines) | *none* | **Zero** |
| Nationality enricher | `glue/scripts/nationality_enricher.py` (828 lines) | `glue/tests/test_nationality_enricher.py` (26 tests) | **Moderate** |
| Glue job trigger | `glue/scripts/trigger_glue.py` (25 lines) | *none* | **Zero** (low risk given simplicity) |
| Lambda freshness checker | `terraform/modules/monitoring/lambda/freshness_checker.py` | `scripts/tests/test_freshness_checker_resilience.py` | **Good** |
| dbt silver models | 10 SQL models | `_silver_schema.yml` (YAML tests) | **Partial** – uniqueness tests disabled on all high-volume tables |
| dbt gold models | 15 SQL models | `_gold_schema.yml` (YAML tests) + 7 custom SQL assertions | **Moderate** – most key columns tested; several analytical models have thin coverage |

The CI pipeline enforces only a **45% coverage floor** for `glue/scripts`, which masks gaps in individual modules.

---

## Priority Areas for Improvement

### 1. `occupancy_kpi_updater.py` – no tests exist

This standalone Glue job is a direct input to the daily occupancy KPI dashboard. It has **zero test coverage** despite containing non-trivial branching logic.

**Functions that should be tested:**

| Function | Why it matters |
|---|---|
| `compute_kpi_for_dates(cursor, target_dates)` | 150-line core function; contains dual-path logic (historical vs. future projection) for 7 separate KPI metrics. A silent mis-calculation here corrupts the occupancy dashboard without any automated signal. |
| `ensure_kpi_table_exists(cursor)` | DDL guard; should verify the exact schema (column names, types, primary key) to prevent silent schema drift. |
| `get_aurora_credentials()` | Module-level `secretsmanager` dependency; should be refactored to accept an injectable client and then tested for both happy-path and rotation/blank-password scenarios (mirroring the existing patterns in `daily_etl.py`). |

**Suggested test scenarios for `compute_kpi_for_dates`:**
- Historical date: verifies applications count, new move-ins (status 4/5/6/7/9), new move-outs (via `moveout_plans_date`), occupancy delta, period start/end rooms, and rate.
- Future date: applications = 0, move-ins use status 4/5 only, move-outs use `moveout_date`, period start pulled from silver snapshot rather than gold record.
- Edge case: no snapshot data → `RuntimeError` raised.
- Edge case: empty `target_dates` list → returns 0 immediately.

---

### 2. `gold_transformer.py` – `compute_occupancy_kpis` is untested

`gold_transformer.py` has 12 functions; only 3 are covered by the existing test file. The most critical gap is `compute_occupancy_kpis()` (lines 461–641, 180 lines).

This function implements the same future/past dual-path KPI logic as `occupancy_kpi_updater.py` but with a different approach for `period_start_rooms` on future dates (it reads from `gold.occupancy_daily_metrics` rather than the silver snapshot). The divergence between the two implementations is itself a testing risk.

**Other untested functions in this file:**

| Function | Risk |
|---|---|
| `cleanup_dbt_tmp_tables(connection, schema)` | Could accidentally drop production tables if the `__dbt_tmp` suffix check is wrong. |
| `create_table_backups(connection, tables, schema)` | Has tests in `test_silver_transformer.py` by reference but not in the gold transformer's own test file. |
| `ensure_occupancy_kpi_table_exists(cursor)` | Schema definition correctness is untested. |
| `main()` | End-to-end orchestration path is never exercised. |

---

### 3. `silver_transformer.py` – placeholder tests should be implemented

`TestMainWorkflow` in `test_silver_transformer.py` contains three test methods that are stubs (`pass`):

```python
def test_full_workflow_success(self, ...):
    pass  # Nothing asserted

def test_validates_staging_dependencies(self):
    pass  # Nothing asserted

def test_handles_dbt_compilation_errors(self):
    pass  # Nothing asserted
```

These give a false sense of coverage. They should be filled in with real assertions or removed.

---

### 4. dbt `stg_inquiries` model – no schema YAML

`dbt/models/silver/stg_inquiries.sql` is the only silver model with no corresponding schema YAML entry. It therefore has:
- No `not_null` tests on any column.
- No `accepted_values` tests.
- No relationship tests to upstream staging tables.

Given that `stg_inquiries` feeds into contract analysis, at minimum the primary key and foreign keys to `stg_apartments` should be validated.

---

### 5. dbt silver models – uniqueness tests disabled without compensating controls

The silver schema YAML documents that uniqueness tests were disabled on five high-volume tables for performance reasons:

```yaml
# unique test disabled - too slow on 25k+ rows (full table scan)
# Enforced by MySQL PRIMARY KEY constraint instead
```

This is a reasonable trade-off, but it means duplicate rows introduced by the ETL (rather than the DB constraint) would not be caught. We should add:

- A lightweight **row-count variance test** (e.g. using `dbt_utils.equal_rowcount` against a prior snapshot or a threshold) to catch unexpected duplication.
- Or a **sampled uniqueness check** that validates uniqueness on a recent date partition rather than the full table.

---

### 6. dbt gold analytical models – minimal column tests

The following gold models have `not_null` on primary columns only and no tests on computed metric columns:

| Model | Missing tests |
|---|---|
| `municipality_churn_weekly` | `net_change` value range, uniqueness on `(week_start, municipality)` |
| `property_churn_weekly` | `net_change` value range, uniqueness on `(week_start, asset_id_hj)` |
| `moveouts_reason_weekly` | `moveout_count >= 0`, uniqueness on `(week_start, moveout_reason_en)` |
| `occupancy_property_daily` | Has uniqueness test, but `occupied_rooms <= total_rooms` is only a `warn`-severity test; consider escalating to `error` |

---

### 7. CI coverage floor should be raised

The current `--cov-fail-under=45` threshold is low enough that the well-tested modules (`daily_etl.py`, `staging_loader.py`) can mask near-zero coverage elsewhere. After addressing gaps 1–3 above, we should raise the floor in steps towards 70%.

---

## Recommended Implementation Order

1. **`occupancy_kpi_updater.py`** – highest business risk, zero coverage. Write tests for `compute_kpi_for_dates` first (past dates, future dates, edge cases), then `ensure_kpi_table_exists`, then refactor `get_aurora_credentials` to be injectable.
2. **`gold_transformer.py` – `compute_occupancy_kpis`** – same KPI logic in a different file; surface any divergence from the standalone updater.
3. **Fill in `TestMainWorkflow` stubs** in `test_silver_transformer.py`.
4. **`stg_inquiries` schema YAML** – low effort, high correctness value.
5. **Raise CI coverage floor** to 60% once 1–3 are done.
6. **dbt gold model metric tests** – add value-range and uniqueness tests to the three analytical models above.
