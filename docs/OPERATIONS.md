# Operations & Runbooks

**Last Updated:** February 11, 2026

This document consolidates all operational procedures, setup guides, and troubleshooting runbooks for the TokyoBeta Data Consolidation project.

---

## 📚 Table of Contents
1. [Setup Guide](#setup-guide)
2. [AWS Profile Management](#aws-profile-management)
3. [Daily Operations](#daily-operations)
4. [Evidence Gold Reporting POC](#evidence-gold-reporting-poc)
5. [Backup & Recovery](#backup--recovery)
6. [Dump Generation](#dump-generation)
7. [Troubleshooting](#troubleshooting)

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

### Security & Access
- Use a dedicated read-only DB user limited to `gold.*`.
- Keep Aurora credentials in `.env` (not committed).
- Use SSL setting `Amazon RDS` in the source connection.

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
2. `ggh_datatransit.sh` executes `mysqldump` against Nazca's RDS
3. Dump compressed and uploaded to `s3://jram-gghouse/dumps/`
4. File size: ~945MB (compressed)
5. Glue ETL downloads at 7:00 AM JST

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
