# Tokyo Beta Data Consolidation

Real estate BI dashboard ETL pipeline for Tokyo Beta property management data.

## 🚨 **START HERE:** New Developer Setup

**⚠️ CRITICAL:** Read `docs/OPERATIONS.md` for AWS profile setup (2 minutes).

This repo ONLY works with AWS account `343881458651` (gghouse profile). Wrong account = AccessDenied errors.

## Quick Start

```bash
# 1. Setup AWS profile enforcement (prevents 90% of issues)
./scripts/setup_direnv.sh

# 2. Restart terminal or source shell config
source ~/.zshrc  # or ~/.bashrc

# 3. Navigate to project (should see confirmation message)
cd /path/to/tokyobeta-data-consolidation

# 4. Login to AWS
aws sso login --profile gghouse

# 5. Verify setup
python3 scripts/validate_full_system.py
```

## Project Overview

**Architecture:** EC2 (dump generation) → S3 (storage) → Glue (ETL) → Aurora MySQL (data warehouse) → QuickSight (BI)

**Data Pipeline:**
```
staging → silver → gold
  ↓        ↓        ↓
Source  Cleaned  Analytics
```

**Daily Schedule (JST):**
- 5:30 AM - EC2 generates SQL dump
- 7:00 AM - Glue ETL runs (staging → silver → gold)
- 8:00 AM - QuickSight dashboard refresh

## Key Documentation

All documentation is located in the `docs/` directory.

### Setup & Operations
- **`docs/OPERATIONS.md`** - **START HERE**. Setup, AWS profile, daily ops, backup/recovery.
- **`docs/PROJECT_STATUS.md`** - Current system health, action items, and roadmap.
- **`docs/DEPLOYMENT.md`** - Deployment verification and security migration plan.

### Architecture & Data
- **`docs/ARCHITECTURE.md`** - ETL pipeline architecture, decisions, and components.
- **`docs/DATA_MODEL.md`** - Schema, data dictionary, business logic, and quality rules.
- **`docs/INCIDENTS.md`** - Incident log, root cause analyses, and lessons learned.
- **`.cursorrules`** - Coding standards and best practices.

## Common Tasks

### Check Data Freshness
```bash
python3 scripts/emergency_staging_fix.py --check-only
```

### Manual Data Load (Emergency)
```bash
# If staging tables are stale
python3 scripts/emergency_staging_fix.py --tables movings tenants rooms
```

### Trigger ETL Manually
```bash
# Trigger full pipeline (respects dependencies)
aws glue start-job-run --job-name tokyobeta-prod-staging-loader --profile gghouse

# Or trigger individual layers (check dependencies!)
aws glue start-job-run --job-name tokyobeta-prod-silver-transformer --profile gghouse
aws glue start-job-run --job-name tokyobeta-prod-gold-transformer --profile gghouse
```

### Validate Full System
```bash
python3 scripts/validate_full_system.py
```

### Evidence Reporting POC (Optional)
```bash
cd evidence
npm install
cp .env.example .env  # fill Aurora read-only credentials
npm run dev
npm run sources
```

POC pages are under `evidence/pages/` and source SQL is under `evidence/sources/aurora_gold/`.

## Project Structure

```
tokyobeta-data-consolidation/
├── .envrc                    # AWS profile auto-config (direnv)
├── dbt/                      # Data transformation models
│   ├── models/
│   │   ├── staging/          # Source views
│   │   ├── silver/           # Cleaned data
│   │   └── gold/             # Business metrics
│   └── seeds/                # Reference data
├── glue/
│   └── scripts/              # ETL job scripts
├── terraform/
│   ├── modules/              # Reusable infrastructure
│   └── environments/prod/    # Production config
├── scripts/                  # Operational scripts
│   ├── emergency_staging_fix.py
│   ├── validate_full_system.py
│   └── deploy_freshness_monitoring.sh
└── docs/                     # Documentation
    ├── OPERATIONS.md         # Setup & Runbooks
    ├── ARCHITECTURE.md       # Design & Components
    ├── DATA_MODEL.md         # Schema & Logic
    ├── INCIDENTS.md          # History & RCA
    ├── DEPLOYMENT.md         # Verification & Security
    └── PROJECT_STATUS.md     # Health & Roadmap
```

## Tech Stack

- **Database:** Aurora MySQL 8.0
- **ETL:** AWS Glue (PySpark + dbt)
- **Storage:** S3
- **Orchestration:** EventBridge
- **BI:** QuickSight
- **IaC:** Terraform
- **Transformation:** dbt

## Development Standards

See `.cursorrules` for comprehensive coding standards, including:
- Test-Driven Development (TDD) - mandatory
- Minimal change philosophy
- Documentation best practices (UPDATE, don't create!)
- Data freshness SLA
- Emergency response procedures

## Monitoring & Alerts

- **CloudWatch Alarms:** Table freshness (> 2 days = alert)
- **Lambda:** Daily freshness checker (9 AM JST)
- **SNS:** Email alerts to jram-ggh@outlook.com
- **Metrics:** `TokyoBeta/DataQuality` namespace

Deploy monitoring:
```bash
./scripts/deploy_freshness_monitoring.sh
```

## Key Metrics

- **Staging Tables:** 130K+ rows (5 tables)
- **Silver Layer:** 12K+ active tenants, 40K+ contracts
- **Gold Layer:** 4K+ days of activity data
- **ETL Duration:** ~25 minutes end-to-end
- **Data Freshness SLA:** < 1 day

## Support & Troubleshooting

**Common Issues:**

1. **AccessDenied errors** → Wrong AWS account
   ```bash
   aws sts get-caller-identity  # Check current account
   aws sso login --profile gghouse  # Login to correct account
   ```

2. **Stale data** → ETL not running
   ```bash
   python3 scripts/emergency_staging_fix.py --check-only
   python3 scripts/emergency_staging_fix.py --tables movings tenants rooms
   ```

3. **direnv not loading** → Shell hook not configured
   ```bash
   ./scripts/setup_direnv.sh
   ```

**See Also:**
- `docs/INCIDENTS.md` - Past incidents and solutions
- `docs/OPERATIONS.md` - Detailed troubleshooting guides

## Contributing

1. Read `.cursorrules` for coding standards
2. Write tests first (TDD mandatory)
3. Update existing docs, don't create new files
4. Test locally before committing
5. Run `terraform plan` before infrastructure changes

## License

Internal project - Tokyo Beta / JRAM GG House

---

**Last Updated:** 2026-02-10  
**Maintained By:** Data Engineering Team  
**Questions?** Check `docs/` or run `python3 scripts/validate_full_system.py`
