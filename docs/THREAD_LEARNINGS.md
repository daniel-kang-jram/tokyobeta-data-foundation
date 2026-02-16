# Thread Learnings (Feb 2026)

## Scope
This document captures concrete learnings from the operational/debugging thread focused on:
- Daily dump availability and continuity (`dumps/gghouse_YYYYMMDD.sql.gz`)
- Glue `tokyobeta-prod-daily-etl` production failures
- dbt failure modes inside Glue
- Run discipline and operator communication

## Key Incidents And Root Causes

### 1) Missing dump date blocked strict continuity runs
- Symptom: runs failed early with continuity check errors for missing `2026-02-15`.
- Impact: daily ETL blocked before staging load.
- Root cause: upstream dump gap existed; strict continuity mode correctly blocked.
- Learning: continuity should be strict by default for data quality, but override mode is required for controlled incident recovery.

### 2) dbt run failed after model builds due to on-run-end auth error
- Example run: `jr_6b72cf7e4b98b338c1bf5a2d3df60c46584d9fe28ff24752d80d006865c9e218` (failed on February 16, 2026).
- Observed pattern:
  - dbt model execution mostly succeeded.
  - failure happened on `on-run-end`.
  - Aurora auth error: `1045 (28000): Access denied for user ...`.
- Learning: this pattern is different from model SQL failure; it is a post-model hook auth/reconnect issue and must be handled separately.

### 3) Regression introduced during auth hardening
- Symptom: immediate failure with:
  - `TypeError: 'NoneType' object is not callable` at `connection.cursor()`
  - followed by `UnboundLocalError: local variable 'cursor' referenced before assignment`
- Root cause:
  - `cursorclass=None` was passed into `pymysql.connect`, overriding default cursor class.
  - cleanup path assumed `cursor` always initialized.
- Learning: changes to DB connection wrappers must include both connection creation tests and failure-path cleanup tests.

## Operational Discipline Learnings

### Mandatory pre-run debrief
Before starting any new Glue run, provide:
1. Exact files changed.
2. Behavioral impact of each change.
3. Test results.
4. Deployment/sync actions completed (S3/terraform).
5. Exact run command to be executed.
6. Explicit go-ahead checkpoint.

### AWS profile consistency
- In this repo, all AWS CLI operations must use `--profile gghouse`.
- Every troubleshooting command and rerun command should include the profile explicitly.

### Failure triage order (fastest signal first)
1. `aws glue get-job-run` for state + top-level error.
2. `/aws-glue/jobs/output` stream for step-level timeline.
3. `/aws-glue/jobs/error` for traceback and dbt/driver exceptions.
4. Validate whether failure is:
   - dump continuity/freshness
   - Aurora credential/auth
   - dbt lock/contention
   - code regression in `daily_etl.py`

## Implementation Changes Added During Thread

### `glue/scripts/daily_etl.py`
- Hardened secret retrieval logic (multiple key formats and version stages).
- Added centralized Aurora connection helper with validation and diagnostics.
- Fixed connection regression (`cursorclass=None` no longer passed).
- Fixed cleanup safety (`cursor` guarded in `finally`).
- Added recoverable handling for dbt `on-run-end`-only `1045` auth pattern.

### `glue/tests/test_daily_etl.py`
- Added tests for:
  - credential resolution fallback behavior
  - empty credential rejection
  - recoverable dbt `on-run-end` auth failure classification

## Guardrails Going Forward
- Do not declare "fixed" from one signal; validate with:
  - local tests
  - script sync confirmation to S3
  - fresh Glue run result
  - CloudWatch step trace for the new run
- Distinguish data-quality blocking failures (missing dumps) from recoverable operational failures (post-model dbt hook auth).
- Maintain strict run communication protocol to avoid silent, surprise production runs.
