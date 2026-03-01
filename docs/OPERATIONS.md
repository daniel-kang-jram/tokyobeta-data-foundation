# Operations & Runbooks

**Last Updated:** March 1, 2026

This document consolidates all operational procedures, setup guides, and troubleshooting runbooks for the TokyoBeta Data Consolidation project.

---

## 📚 Table of Contents
1. [Setup Guide](#setup-guide)
2. [AWS Profile Management](#aws-profile-management)
3. [Daily Operations](#daily-operations)
4. [Evidence Gold Reporting POC](#evidence-gold-reporting-poc)
5. [Backup & Recovery](#backup--recovery)
6. [Dump Generation](#dump-generation)
7. [Reliability Guardrails](#reliability-guardrails-feb-2026-hardening)
8. [Ownership Matrix](#ownership-matrix-upstream-vs-jram)
9. [Troubleshooting](#troubleshooting)
10. [Test Coverage & Quality](#test-coverage--quality)

---

## Setup Guide

### Prerequisites
1. **direnv** - For automatic AWS profile management
2. **AWS CLI v2** - With SSO configured
3. **Python 3.11+** - For scripts and Lambda functions
4. **Terraform 1.5+** - For infrastructure management
5. **dbt 1.6+** - For data transformations

### Quick Start (5 minutes)

#### 1. Install direnv
```bash
brew install direnv  # macOS
# OR
sudo apt-get install direnv  # Linux
```

#### 2. Enable direnv in Your Shell
```bash
# For zsh (macOS default)
echo 'eval "$(direnv hook zsh)"' >> ~/.zshrc
source ~/.zshrc

# For bash
echo 'eval "$(direnv hook bash)"' >> ~/.bashrc
source ~/.bashrc
```

#### 3. Allow direnv for This Repo
```bash
cd /Users/danielkang/tokyobeta-data-consolidation
direnv allow
```
You should see: `✅ AWS Profile set to: gghouse (Account: 343881458651)`

#### 4. Authenticate with AWS SSO
```bash
aws sso login --profile gghouse
```

#### 5. Verify Setup
```bash
# Check AWS profile
aws sts get-caller-identity
# Should show: Account 343881458651

# Check S3 access
aws s3 ls s3://jram-gghouse/dumps/ | tail -5

# Check database access
python3 scripts/emergency_staging_fix.py --check-only
```

---

## AWS Profile Management

**CRITICAL:** This repo ONLY works with AWS account `343881458651` (gghouse profile).

### Why It Matters
Using the wrong AWS profile (default, jram, etc.) will cause:
- ❌ AccessDenied errors on S3, Glue, RDS
- ❌ Terraform failures
- ❌ Scripts unable to access resources

### How It Works
When you `cd` into this repository, `direnv` automatically:
1. Reads `.envrc` file
2. Sets environment variables:
   - `AWS_PROFILE=gghouse`
   - `AWS_DEFAULT_PROFILE=gghouse`
   - `AWS_REGION=ap-northeast-1`
3. Displays confirmation message

### Manual Override (Not Recommended)
If you cannot use direnv, manually set profile before each command:
```bash
export AWS_PROFILE=gghouse
```

---

## Daily Operations

### Morning Routine (Every Day)
```bash
# 1. Navigate to project (direnv loads automatically)
cd /Users/danielkang/tokyobeta-data-consolidation

# 2. Re-authenticate if needed (SSO expires after 8 hours)
aws sso login --profile gghouse

# 3. Check data freshness
python3 scripts/emergency_staging_fix.py --check-only
```

### Common Tasks

#### Check Staging Table Freshness
```bash
python3 scripts/emergency_staging_fix.py --check-only
```

#### Load Latest Dump Manually (Emergency)
```bash
# If staging tables are stale
python3 scripts/emergency_staging_fix.py --tables movings tenants rooms inquiries
```

#### Trigger Glue Jobs Manually
```bash
# Staging loader
aws glue start-job-run --job-name tokyobeta-prod-staging-loader

# Silver transformer
aws glue start-job-run --job-name tokyobeta-prod-silver-transformer

# Gold transformer
aws glue start-job-run --job-name tokyobeta-prod-gold-transformer
```

---

## Evidence Gold Reporting POC

### Scope
The Evidence proof-of-concept starts with:
- `gold.occupancy_daily_metrics` for occupancy trend and net movement drivers
- `gold.new_contracts` for move-in profiling
- `gold.moveouts` for move-out profiling

Additional marts used by the redesigned dashboards:
- `gold.occupancy_kpi_meta` (as-of snapshot boundary + freshness)
- `gold.dim_property` + `gold.occupancy_property_map_latest` (Tokyo map)
- `gold.movein_analysis` + weekly cubes (`gold.move_events_weekly`, `gold.*_churn_weekly`, `gold.moveouts_reason_weekly`)

Dimensions covered in the POC:
- tenant type (`tenant_type`: corporate/individual)
- nationality
- property (`apartment_name`)
- municipality

Time grains:
- Occupancy: daily (with explicit fact vs projection boundary)
- Move-in / Move-out profiling: weekly (Monday-start)

### Runbook (Local)
```bash
cd /Users/danielkang/tokyobeta-data-consolidation/evidence
npm install
cp .env.example .env
# Fill EVIDENCE_SOURCE__aurora_gold__* values with read-only Aurora credentials
npm run dev
npm run sources
```

### Evidence gold refresh verification

Use this acceptance flow after any page-source update or incident response.

#### 1. Build and page contract smoke check
```bash
cd /Users/danielkang/tokyobeta-data-consolidation/evidence
npm run build
rg -n "from aurora_gold\\.(kpi_month_end_metrics|kpi_reference_trace|funnel_application_to_movein_periodized|funnel_application_to_movein_segment_share|movein_profile_monthly|moveout_profile_monthly|municipality_churn_weekly|property_churn_weekly)" \
  pages/index.md pages/funnel.md pages/geography.md pages/pricing.md pages/moveins.md pages/moveouts.md
```

Expected output:
- `pages/index.md` includes `kpi_month_end_metrics` and `kpi_reference_trace`.
- `pages/funnel.md` includes `funnel_application_to_movein_periodized`.
- `pages/pricing.md` includes `funnel_application_to_movein_segment_share`.
- `pages/geography.md`, `pages/moveins.md`, and `pages/moveouts.md` point only to aurora_gold-backed marts.

#### 2. Parity-critical page-to-source mapping

| Page | Required source contracts |
| --- | --- |
| `index.md` | `aurora_gold.kpi_month_end_metrics`, `aurora_gold.kpi_reference_trace` |
| `funnel.md` | `aurora_gold.funnel_application_to_movein_periodized`, `aurora_gold.funnel_application_to_movein_daily` |
| `geography.md` | `aurora_gold.municipality_churn_weekly`, `aurora_gold.property_churn_weekly` |
| `pricing.md` | `aurora_gold.funnel_application_to_movein_segment_share`, `aurora_gold.funnel_application_to_movein_periodized` |
| `moveins.md` | `aurora_gold.movein_profile_monthly`, `aurora_gold.move_events_weekly` |
| `moveouts.md` | `aurora_gold.moveout_profile_monthly`, `aurora_gold.move_events_weekly` |

#### 3. Timestamp and freshness label validation
```bash
cd /Users/danielkang/tokyobeta-data-consolidation/evidence
rg -n "Time basis:|Freshness:" \
  pages/index.md pages/funnel.md pages/geography.md pages/pricing.md pages/moveins.md pages/moveouts.md
```

Expected output:
- Every listed page returns both `Time basis:` and `Freshness:` labels.
- If either label is missing for any page, treat release as parity-incomplete and block deployment.

#### 4. Operator CSV export checks
```bash
cd /Users/danielkang/tokyobeta-data-consolidation/evidence
rg -n "downloadable=\\{true\\}" \
  pages/funnel.md pages/pricing.md pages/moveins.md pages/moveouts.md pages/geography.md
```

Expected output:
- Core operational detail tables are CSV-exportable on parity pages.
- `pricing.md`, `moveins.md`, and `moveouts.md` must always return at least one downloadable table each.
- `geography.md` detail tables should remain exportable for incident triage.

### Security & Access
- Use a dedicated read-only DB user limited to `gold.*`.
- Keep Aurora credentials in `.env` (not committed).
- Use SSL setting `Amazon RDS` in the source connection.

#### Dashboard Login Protection (CloudFront)
- Both Evidence endpoints use CloudFront viewer-request authentication:
  - Gold-connected dashboard: `https://d2lnx09sw8wka0.cloudfront.net/`
  - Snapshot dashboard: `https://d20nv2k4q5ngoc.cloudfront.net/`
- Auth mode is a dedicated branded login page (`/__auth/login`) rather than browser popup Basic Auth.
- Session cookie: `evidence_session` (HttpOnly, Secure, SameSite=Lax, max age 8 hours).
- Logout endpoint: `GET /__auth/logout` (clears session and redirects to login page).
- Open-redirect protection: login `return_to` accepts only relative paths under `/`.
- Retired endpoint: `https://d3c81kja45lr6l.cloudfront.net/` is not an active distribution.

### Success Criteria (Hobby Feasibility)
1. **Connectivity:** Aurora connection is stable over repeated source runs.
2. **Performance:** `npm run sources` completes within agreed window.
3. **Usability:** key pages load fast enough for analyst workflow.
4. **Analytical fit:** required breakdowns are accurate and actionable.

### Decision Gate: Move to Self-Hosted Evidence on AWS When
- Cloud-hosted access cannot reach private Aurora network.
- Source extraction or page interactivity does not meet team SLA.
- You need tighter security controls (private VPC-only traffic, AWS-native secrets).

### Self-Hosted Target Pattern
- Deploy Evidence app on AWS (same VPC or peered VPC with Aurora).
- Keep Aurora private; allow security-group to security-group access only.
- Store source credentials in Secrets Manager and inject as env vars.
- Reuse the same `evidence/` project and source SQL files.

---

## Backup & Recovery

### Strategy Overview
We use Aurora's built-in automated backups instead of expensive manual snapshots.
- **Automated daily backups** (7-day retention)
- **Point-in-Time Recovery (PITR)** to any second in the last 7 days
- **Cost:** $0 extra (included in RDS pricing)

### Recovery Scenarios

#### Scenario 1: ETL Failed, Need to Rollback
**Problem**: Glue job failed during dbt transformations, data corrupted.
**Solution**: Use Point-in-Time Recovery (PITR).

```bash
# Restore to 1 hour ago (before ETL started)
./scripts/rollback_etl.sh "$(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ)"

# Or restore to specific time
./scripts/rollback_etl.sh "2026-02-04T10:00:00Z"
```

#### Scenario 2: Need to Check Previous State
**Problem**: Need to investigate data state from previous day.
**Solution**: Create read-only clone from automated backup.

```bash
aws rds restore-db-cluster-to-point-in-time \
    --db-cluster-identifier tokyobeta-prod-aurora-cluster-public-investigation \
    --source-db-cluster-identifier tokyobeta-prod-aurora-cluster-public \
    --restore-to-time "2026-02-04T00:00:00Z" \
    --profile gghouse
```

#### Scenario 3: Pre-Migration Snapshot
**Problem**: About to run major schema migration, want explicit snapshot.
**Solution**: Create manual snapshot (rare case).

```bash
aws rds create-db-cluster-snapshot \
    --db-cluster-snapshot-identifier tokyobeta-prod-pre-migration-$(date +%Y%m%d) \
    --db-cluster-identifier tokyobeta-prod-aurora-cluster-public \
    --profile gghouse
```

---

## Dump Generation

### Current Production Setup
**Daily at 5:30 AM JST:**
1. EC2 instance (`i-00523f387117d497b`) runs cron job
2. `/home/ubuntu/rds-backup/ggh_datatransit.sh` reads source credentials from `tokyobeta/prod/rds/cron-credentials`
3. Script hard-fails if secret fields (`host/database/username/password/port`) are missing or preflight checks fail
4. Primary dump is uploaded to `s3://jram-gghouse/dumps/gghouse_YYYYMMDD.sql`
5. Per-day manifest is uploaded to `s3://jram-gghouse/dumps-manifest/gghouse_YYYYMMDD.json`
6. Glue daily ETL requires a manifest-valid dump candidate before staging load

### Dump Contract (Prod)

- Required secret: `tokyobeta/prod/rds/cron-credentials`
- Required dump key: `dumps/gghouse_YYYYMMDD.sql`
- Required manifest key: `dumps-manifest/gghouse_YYYYMMDD.json`
- Required manifest fields:
  - `source_host`
  - `source_database`
  - `run_id`
  - `dump_sha256`
  - `valid_for_etl`
  - `max_updated_at_by_table` (or backward-compatible `source_table_max_updated_at`)

### Quarantine Policy (Feb 2026 Recovery)

- Recovery baseline: `2026-02-18`
- Quarantine window: `2026-02-11` to `2026-02-17`
- Missing dumps (`20260211`, `20260212`, `20260215`) are represented with invalid manifests (`valid_for_etl=false`)
- Invalid-source dumps are preserved under:
  - `s3://jram-gghouse/quarantine/raw-source-mismatch/20260218/`
- Quarantine index:
  - `s3://jram-gghouse/dumps-manifest/quarantine_index_20260211_20260217_20260218_113139.json`

### Verification Commands

```bash
# Check latest dump object
aws s3 ls s3://jram-gghouse/dumps/ | tail -5

# Check latest manifest
aws s3 cp s3://jram-gghouse/dumps-manifest/gghouse_$(date +%Y%m%d).json - | jq

# Confirm alert subscribers
aws sns list-subscriptions-by-topic \
  --topic-arn arn:aws:sns:ap-northeast-1:343881458651:tokyobeta-prod-dashboard-etl-alerts \
  --profile gghouse
```

### Alternatives (Documented but Not Implemented)

#### 1. AWS DMS (Database Migration Service)
- **Benefits:** Real-time data (CDC), no EC2 dependency.
- **Status:** Documented in `docs/DMS_VENDOR_REQUIREMENTS.md`, not implemented.
- **Trigger:** If business needs real-time data (< 1 hour latency).

#### 2. Secure EC2 Cron
- **Benefits:** Uses Secrets Manager + IAM roles (no hardcoded credentials).
- **Status:** Documented in `docs/SECURITY_MIGRATION_PLAN.md`, not implemented.
- **Trigger:** If security audit requires credential management.

---

## Reliability Guardrails (Feb 2026 Hardening)

### Daily ETL Archive Behavior
- `10_archive_processed_dump` is now non-critical by default.
- `archive_processed_dump` logs warning and continues on copy/tagging errors unless strict mode is enabled.
- Strict mode can be enabled only with `DAILY_FAIL_ON_ARCHIVE_ERROR=true`.

### Glue Failure Alerting (Primary + Secondary)
- Primary: EventBridge rule `tokyobeta-prod-glue-job-state-failures` captures Glue `FAILED`/`TIMEOUT` and publishes to SNS.
- Secondary: CloudWatch metric alarms remain enabled, with corrected dimensions (`JobName`, `JobRunId=ALL`, `Type=count`) and `treat_missing_data=notBreaching`.
- SNS recipients are Terraform-managed from merged set of `alert_email` + `alert_emails`.

### Controlled Failure Drill (Required after alert changes)
- Goal: prove Glue `FAILED` state reaches SNS and both email endpoints.
- Safety: do not touch external V3 sync; test only `tokyobeta-prod-daily-etl` runtime args.

```bash
# 1) Trigger intentional Glue failure (invalid secret ARN override)
aws glue start-job-run \
  --job-name tokyobeta-prod-daily-etl \
  --arguments '{
    "--DAILY_TARGET_DATE":"2026-02-22",
    "--AURORA_SECRET_ARN":"arn:aws:secretsmanager:ap-northeast-1:343881458651:secret:tokyobeta/prod/aurora/credentials-INTENTIONAL-FAIL"
  }' \
  --profile gghouse

# 2) Wait for terminal FAILED state
aws glue get-job-run \
  --job-name tokyobeta-prod-daily-etl \
  --run-id <RUN_ID_FROM_STEP_1> \
  --query 'JobRun.{State:JobRunState,Error:ErrorMessage,Started:StartedOn,Completed:CompletedOn}' \
  --output json \
  --profile gghouse

# 3) Verify EventBridge invocation for failure rule
aws cloudwatch get-metric-statistics \
  --namespace AWS/Events \
  --metric-name Invocations \
  --dimensions Name=RuleName,Value=tokyobeta-prod-glue-job-state-failures \
  --statistics Sum \
  --period 60 \
  --start-time <UTC-START> \
  --end-time <UTC-END> \
  --profile gghouse

# 4) Verify SNS publish + delivery (expect publish=1, delivered=2 for two recipients)
aws cloudwatch get-metric-statistics \
  --namespace AWS/SNS \
  --metric-name NumberOfMessagesPublished \
  --dimensions Name=TopicName,Value=tokyobeta-prod-dashboard-etl-alerts \
  --statistics Sum \
  --period 60 \
  --start-time <UTC-START> \
  --end-time <UTC-END> \
  --profile gghouse

aws cloudwatch get-metric-statistics \
  --namespace AWS/SNS \
  --metric-name NumberOfNotificationsDelivered \
  --dimensions Name=TopicName,Value=tokyobeta-prod-dashboard-etl-alerts \
  --statistics Sum \
  --period 60 \
  --start-time <UTC-START> \
  --end-time <UTC-END> \
  --profile gghouse
```

- Acceptance criteria:
  - Glue run reaches `FAILED`.
  - EventBridge failure rule shows `Invocations >= 1` in the test window.
  - SNS metrics show `NumberOfMessagesPublished >= 1`.
  - SNS metrics show `NumberOfNotificationsDelivered >= 2`.
  - Inbox confirmation from both recipients (`daniel.kang@jram.jp`, `jram-ggh@outlook.com`).

### Freshness Checker Runtime Contract
- Lambda layer `pymysql_layer.zip` is mandatory and attached in Terraform.
- Missing `pymysql` is a hard runtime failure (no degraded success path).
- Post-deploy smoke check validates `db_checks_skipped=false`.

### Immutable Artifact Release Contract
- Deploy uploads Glue/dbt artifacts under immutable prefixes:
  - `s3://jram-gghouse/glue-scripts/releases/<commit-sha>/`
  - `s3://jram-gghouse/dbt-project/releases/<commit-sha>/`
- Glue jobs run against release-specific paths, so Terraform apply failure does not break active runtime.
- Deploy workflow now includes post-deploy conformance checks:
  - Glue IAM tagging actions present
  - Freshness Lambda has attached layer
  - EventBridge Glue-failure rule targets SNS
  - Both required SNS email endpoints are confirmed

---

## Ownership Matrix (Upstream vs JRAM)

### JRAM Self-Healable (Same Day)
- Basis security-group allowlist drift (CIDR/IP changes in Terraform/live SG)
- Glue IAM policy gaps (including S3 object tagging permissions)
- Glue script/runtime bugs and archive-step behavior
- Monitoring/alert routing (EventBridge/CloudWatch/SNS subscriptions)
- Freshness checker runtime packaging and Lambda layer attachment

### External Action Required
- V3 -> basis upstream sync process execution/restart
- Upstream-side sync SQL/logic failures
- Upstream-side source DB connectivity inside V3 environment

### Upstream Staleness Rule
- Freshness checker validates `max_updated_at_by_table` from latest dump manifest for:
  - `movings`, `tenants`, `rooms`, `apartments`
- `inquiries` is excluded from upstream recency incident gating.
- If lag exceeds threshold (`UPSTREAM_SYNC_STALE_HOURS`, prod default 24h), checker emits critical alert.

---

## Troubleshooting

### AWS AccessDenied Errors
**Cause:** Wrong AWS profile or expired SSO session.
**Solution:**
```bash
# Check current profile
aws sts get-caller-identity

# If wrong account, ensure direnv loaded
cd /Users/danielkang/tokyobeta-data-consolidation
direnv allow

# Re-authenticate
aws sso login --profile gghouse
```

### Stale Data (Tables Not Updating)
**Cause:** Glue jobs not running or failed.
**Solution:**
1. Check if S3 dumps are current: `aws s3 ls s3://jram-gghouse/dumps/ | tail -5`
2. Load manually: `python3 scripts/emergency_staging_fix.py --tables movings tenants rooms`
3. Trigger downstream jobs:
   ```bash
   aws glue start-job-run --job-name tokyobeta-prod-silver-transformer
   aws glue start-job-run --job-name tokyobeta-prod-gold-transformer
   ```

### direnv Not Working
**Cause:** direnv not installed or shell hook not loaded.
**Solution:**
1. Install direnv: `brew install direnv`
2. Add hook to shell rc file
3. Allow for this repo: `direnv allow`

---

## Physical-Room Occupancy Recovery (Feb 2026 Corrupted Window)

### Runtime Contracts
- `DAILY_FORCE_REBUILD_SNAPSHOT_DATE` (optional `YYYY-MM-DD`)
  - Passed to dbt as `force_rebuild_snapshot_date`.
  - `silver.tenant_room_snapshot_daily` deletes and reinserts that snapshot date on incremental runs.
- `DAILY_OCCUPANCY_REBUILD_START_DATE` (optional `YYYY-MM-DD`)
  - Expands occupancy recompute start date deterministically.
- `DAILY_MAX_DUMP_STALE_DAYS=0` in production Glue defaults.
  - Daily ETL fails when same-day dump is not available.

### Occupancy KPI Rules (gold.occupancy_daily_metrics)
- Fact-day `period_end_rooms` uses physical-room distinct count from silver:
  - `COUNT(DISTINCT CONCAT(apartment_id, '-', room_id))`
  - status set: `(7, 9, 10, 11, 12, 13, 14, 15)`
- Date-quality gap dates are skipped.
- Bridge-day rule:
  - if previous calendar date is gap, set `period_start_rooms = NULL` for first non-gap day.

### Corrupted Window Override Policy
- Forced valid range: `2026-02-04` to `2026-02-10`
- Forced gap range: `2026-02-11` to `2026-02-18`
- These overrides are upserted into `gold.data_quality_calendar` on each daily ETL run.

### One-Time Recovery Commands
```bash
# 1) Quarantine 2026-02-18 dump + manifest before invalidation
aws s3 cp s3://jram-gghouse/dumps/gghouse_20260218.sql \
  s3://jram-gghouse/quarantine/manual-corrupt-window-2026-02-11-to-2026-02-18/dumps/gghouse_20260218.sql \
  --profile gghouse

aws s3 cp s3://jram-gghouse/dumps-manifest/gghouse_20260218.json \
  s3://jram-gghouse/quarantine/manual-corrupt-window-2026-02-11-to-2026-02-18/dumps-manifest/gghouse_20260218.json \
  --profile gghouse

# 2) Force rebuild snapshot + occupancy recompute from 2026-02-04
aws glue start-job-run \
  --job-name tokyobeta-prod-daily-etl \
  --arguments '{
    "--DAILY_TARGET_DATE":"2026-02-19",
    "--DAILY_FORCE_REBUILD_SNAPSHOT_DATE":"2026-02-19",
    "--DAILY_OCCUPANCY_REBUILD_START_DATE":"2026-02-04"
  }' \
  --profile gghouse
```

### Validation Queries
```sql
-- Gold coverage restored for valid dates
SELECT snapshot_date
FROM gold.occupancy_daily_metrics
WHERE snapshot_date BETWEEN '2026-02-04' AND '2026-02-10'
ORDER BY snapshot_date;

-- Quarantine dates excluded
SELECT snapshot_date
FROM gold.occupancy_daily_metrics
WHERE snapshot_date BETWEEN '2026-02-11' AND '2026-02-18'
ORDER BY snapshot_date;

-- Physical-room count reconciliation
SELECT
  s.snapshot_date,
  COUNT(DISTINCT CONCAT(s.apartment_id, '-', s.room_id)) AS physical_rooms
FROM silver.tenant_room_snapshot_daily s
WHERE s.snapshot_date BETWEEN '2026-02-19' AND '2026-02-22'
  AND s.management_status_code IN (7, 9, 10, 11, 12, 13, 14, 15)
GROUP BY s.snapshot_date
ORDER BY s.snapshot_date;
```

---

## Test Coverage & Quality

### Current Coverage Landscape

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

### Priority Areas for Improvement

#### 1. `occupancy_kpi_updater.py` – no tests exist

This standalone Glue job is a direct input to the daily occupancy KPI dashboard. It has **zero test coverage** despite containing non-trivial branching logic.

| Function | Why it matters |
|---|---|
| `compute_kpi_for_dates(cursor, target_dates)` | 150-line core function; contains dual-path logic (historical vs. future projection) for 7 separate KPI metrics. A silent mis-calculation here corrupts the occupancy dashboard without any automated signal. |
| `ensure_kpi_table_exists(cursor)` | DDL guard; should verify the exact schema (column names, types, primary key) to prevent silent schema drift. |
| `get_aurora_credentials()` | Module-level `secretsmanager` dependency; should be refactored to accept an injectable client and then tested for both happy-path and rotation/blank-password scenarios (mirroring the existing patterns in `daily_etl.py`). |

Suggested test scenarios for `compute_kpi_for_dates`:
- Historical date: verifies applications count, new move-ins (status 4/5/6/7/9), new move-outs (via `moveout_plans_date`), occupancy delta, period start/end rooms, and rate.
- Future date: applications = 0, move-ins use status 4/5 only, move-outs use `moveout_date`, period start pulled from silver snapshot rather than gold record.
- Edge case: no snapshot data → `RuntimeError` raised.
- Edge case: empty `target_dates` list → returns 0 immediately.

#### 2. `gold_transformer.py` – `compute_occupancy_kpis` is untested

`gold_transformer.py` has 12 functions; only 3 are covered by the existing test file. The most critical gap is `compute_occupancy_kpis()` (lines 461–641, 180 lines).

This function implements the same future/past dual-path KPI logic as `occupancy_kpi_updater.py` but with a different approach for `period_start_rooms` on future dates (it reads from `gold.occupancy_daily_metrics` rather than the silver snapshot). The divergence between the two implementations is itself a testing risk.

Other untested functions:

| Function | Risk |
|---|---|
| `cleanup_dbt_tmp_tables(connection, schema)` | Could accidentally drop production tables if the `__dbt_tmp` suffix check is wrong. |
| `create_table_backups(connection, tables, schema)` | Has tests in `test_silver_transformer.py` by reference but not in the gold transformer's own test file. |
| `ensure_occupancy_kpi_table_exists(cursor)` | Schema definition correctness is untested. |
| `main()` | End-to-end orchestration path is never exercised. |

#### 3. `silver_transformer.py` – placeholder tests should be implemented

`TestMainWorkflow` in `test_silver_transformer.py` contains three test methods that are stubs (`pass`):

```python
def test_full_workflow_success(self, ...):
    pass  # Nothing asserted

def test_validates_staging_dependencies(self):
    pass  # Nothing asserted

def test_handles_dbt_compilation_errors(self):
    pass  # Nothing asserted
```

These give a false sense of coverage and should be filled in with real assertions or removed.

#### 4. dbt `stg_inquiries` model – no schema YAML

`dbt/models/silver/stg_inquiries.sql` is the only silver model with no corresponding schema YAML entry. It therefore has no `not_null`, `accepted_values`, or relationship tests. At minimum the primary key and foreign keys to `stg_apartments` should be validated.

#### 5. dbt silver models – uniqueness tests disabled without compensating controls

Uniqueness tests were disabled on five high-volume tables for performance reasons (`# unique test disabled - too slow on 25k+ rows`). This is a reasonable trade-off, but duplicate rows introduced by the ETL would not be caught. We should add either:

- A lightweight **row-count variance test** (e.g. `dbt_utils.equal_rowcount` against a prior snapshot or a threshold).
- Or a **sampled uniqueness check** that validates uniqueness on a recent date partition rather than the full table.

#### 6. dbt gold analytical models – minimal column tests

| Model | Missing tests |
|---|---|
| `municipality_churn_weekly` | `net_change` value range, uniqueness on `(week_start, municipality)` |
| `property_churn_weekly` | `net_change` value range, uniqueness on `(week_start, asset_id_hj)` |
| `moveouts_reason_weekly` | `moveout_count >= 0`, uniqueness on `(week_start, moveout_reason_en)` |
| `occupancy_property_daily` | Has uniqueness test, but `occupied_rooms <= total_rooms` is only a `warn`-severity test; consider escalating to `error` |

#### 7. CI coverage floor should be raised

The current `--cov-fail-under=45` threshold is low enough that well-tested modules (`daily_etl.py`, `staging_loader.py`) can mask near-zero coverage elsewhere. After addressing gaps 1–3 above, raise the floor in steps towards 70%.

### Recommended Implementation Order

1. **`occupancy_kpi_updater.py`** – highest business risk, zero coverage. Write tests for `compute_kpi_for_dates` first (past dates, future dates, edge cases), then `ensure_kpi_table_exists`, then refactor `get_aurora_credentials` to be injectable.
2. **`gold_transformer.py` – `compute_occupancy_kpis`** – same KPI logic in a different file; surface any divergence from the standalone updater.
3. **Fill in `TestMainWorkflow` stubs** in `test_silver_transformer.py`.
4. **`stg_inquiries` schema YAML** – low effort, high correctness value.
5. **Raise CI coverage floor** to 60% once 1–3 are done.
6. **dbt gold model metric tests** – add value-range and uniqueness tests to the three analytical models above.
