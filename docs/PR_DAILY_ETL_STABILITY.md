# PR: Harden Daily ETL Against Stale Dumps and Lock Contention

## Summary
This PR implements the immediate stability fixes for the daily monolithic ETL path:
- Prevent stale dump reprocessing in `daily_etl.py`
- Reduce dbt write contention by lowering prod threads
- Replace lock-heavy incremental predicate in `tenant_room_snapshot_daily`
- Increase `daily-etl` Glue capacity via Terraform (`G.2X`, 120 min)
- Fix SQL typo in `tenant_status_history`

## Why
Recent failures were caused by lock contention and stale input reprocessing:
- `tenant_room_snapshot_daily` incremental filter used `NOT IN (SELECT DISTINCT ...)` over a large table
- dbt prod execution used 8 threads against Aurora
- `daily-etl` retried already-processed dumps
- `daily-etl` runtime budget was too tight for the full monolithic sequence

## Changes
### 1) Dump freshness guard (skip stale reruns)
- **File:** `glue/scripts/daily_etl.py`
- Added:
  - `get_processed_dump_key(source_key)`
  - `is_dump_already_processed(source_key)`
- Updated `main()` to short-circuit and `job.commit()` when latest dump already exists under `processed/`.
- Updated `archive_processed_dump()` to reuse `get_processed_dump_key()`.

### 2) Lower dbt prod concurrency
- **File:** `dbt/profiles.yml`
- Changed `prod.threads` from `8` to `2`.

### 3) Improve incremental predicate
- **File:** `dbt/models/silver/tenant_room_snapshot_daily.sql`
- Changed incremental filter from:
  - `snapshot_date NOT IN (SELECT DISTINCT snapshot_date FROM {{ this }})`
- To:
  - `snapshot_date > COALESCE((SELECT MAX(snapshot_date) FROM {{ this }}), CAST('1900-01-01' AS DATE))`

### 4) Increase monolith Glue capacity
- **File:** `terraform/modules/glue/main.tf`
  - `aws_glue_job.daily_etl` now uses `var.job_timeout`, `var.worker_type`, `var.number_of_workers`.
- **File:** `terraform/environments/prod/main.tf`
  - Set module inputs to `worker_type = "G.2X"` and `job_timeout = 120`.

### 5) SQL typo fix
- **File:** `dbt/models/silver/tenant_status_history.sql`
- Fixed `sp.        dbt_updated_at` to `sp.dbt_updated_at`.

## Test Evidence
### Code-level
1. `python -m py_compile glue/scripts/daily_etl.py`
   - Result: pass
2. `pytest -q glue/tests/test_daily_etl.py`
   - Result: `5 passed in 0.26s`
   - Includes new tests for:
     - processed key mapping
     - stale dump detection true-path
     - stale dump detection missing-key path (404)

### Terraform-level
1. `terraform -chdir=terraform/environments/prod init -input=false -no-color`
   - Result: pass
2. `terraform -chdir=terraform/environments/prod validate -no-color`
   - Result: pass
3. `AWS_PROFILE=gghouse terraform -chdir=terraform/environments/prod plan -input=false -no-color -out=codex-glue-upgrade.tfplan`
   - Result: pass (full plan surfaced unrelated pending changes outside this PR scope)
   - Not applied from full plan: changes in Aurora final snapshot id, Evidence CloudFront TLS/policy, and Aurora SG ingress.
4. `AWS_PROFILE=gghouse terraform -chdir=terraform/environments/prod plan -input=false -no-color -target=module.glue.aws_glue_job.daily_etl -out=codex-daily-etl-only.tfplan`
   - Result: pass (`1 to change`: `timeout 60 -> 120`, `worker_type G.1X -> G.2X`)
5. `AWS_PROFILE=gghouse terraform -chdir=terraform/environments/prod apply -input=false -no-color codex-daily-etl-only.tfplan`
   - Result: pass (`0 added, 1 changed, 0 destroyed`)
6. `AWS_PROFILE=gghouse terraform -chdir=terraform/environments/prod plan -input=false -no-color -target=module.glue.aws_glue_job.daily_etl`
   - Result: pass (`No changes`)

### Deployment-level verification
1. `aws glue get-job --job-name tokyobeta-prod-daily-etl --profile gghouse`
   - Verified:
     - `Timeout: 120`
     - `WorkerType: G.2X`
2. Uploaded Glue script:
   - `aws s3 cp glue/scripts/daily_etl.py s3://jram-gghouse/glue-scripts/daily_etl.py --profile gghouse`
   - Verified with `head-object`:
     - `LastModified: 2026-02-13T02:48:15+00:00`
     - `ETag: "0ef0d073c16080bdfa9bc94312267a46"` (matches local md5)
3. Uploaded dbt artifacts:
   - `dbt/profiles.yml` -> `s3://jram-gghouse/dbt-project/profiles.yml`
   - `dbt/models/silver/tenant_room_snapshot_daily.sql` -> `s3://jram-gghouse/dbt-project/models/silver/tenant_room_snapshot_daily.sql`
   - `dbt/models/silver/tenant_status_history.sql` -> `s3://jram-gghouse/dbt-project/models/silver/tenant_status_history.sql`
   - Verified with `head-object` (`LastModified` and `ETag` match local md5 for each file)

## Deployment Status
- Targeted Terraform apply for `module.glue.aws_glue_job.daily_etl` completed successfully.
- Live Glue job now runs with:
  - `timeout = 120`
  - `worker_type = G.2X`
- Updated Glue/dbt artifacts were uploaded to S3 and verified.

## Required Follow-up to Deploy
1. Run a full non-targeted Terraform reconciliation after reviewing unrelated pending infra changes (seen in full plan).
2. (Optional) Trigger one manual `tokyobeta-prod-daily-etl` run to validate end-to-end behavior under new settings.

## Risk / Rollback
- Risk: low to medium (runtime behavior change is additive guard + safer predicate + reduced parallelism).
- Rollback:
  - Revert this PR and redeploy Terraform/Glue script.
  - For emergency data recovery, use existing Aurora PITR strategy.
