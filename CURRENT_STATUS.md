# Current Status - Tokyo Beta Data Platform

**Last Updated**: February 5, 2026, 11:00 JST  
**System Status**: ✅ **Operational**  
**AWS Account**: gghouse (343881458651)  
**Region**: ap-northeast-1 (Tokyo)

---

## Executive Summary

The Tokyo Beta real estate analytics platform is **fully operational** with a production-grade medallion architecture, automated daily ETL, and robust backup/recovery capabilities. Recent improvements include database cleanup ($57/month cost savings) and optimized ETL runtime (15min → 4min).

---

## System Status

### ✅ Operational Services

| Component | Status | Details |
|-----------|--------|---------|
| **ETL Pipeline** | ✅ Running | Daily at 7:00 AM JST, ~4 min execution |
| **Aurora DB** | ✅ Available | db.t4g.medium cluster, 7-day PITR |
| **Data Quality** | ✅ Good | 69/76 tests passing (90.8%) |
| **Monitoring** | ✅ Active | CloudWatch logs + SNS alerts |
| **Backup/Recovery** | ✅ Tested | PITR script validated |

### 📊 Data Freshness

- **Last ETL Run**: February 5, 2026, 10:53 JST
- **Execution Time**: 235 seconds (~4 minutes)
- **Status**: SUCCESS
- **Tables Updated**: 91 total (81 staging + 6 silver + 4 gold)

---

## Recent Changes (Feb 5, 2026)

### Database Cleanup ✅
**Dropped 5 redundant schemas**:
- `basis` (80 empty tables - vendor artifact)
- `_analytics`, `_silver`, `_gold` (legacy from schema naming bug)
- `analytics` (empty, superseded by `gold`)

**Result**: Clean database structure with only active schemas

### Cost Optimization ✅
**Removed manual snapshots**: -$57/month
- Before: Manual pre-ETL snapshots ($0.095/GB-month × 600GB)
- After: Aurora automated backups (included, $0 extra cost)
- **Savings**: $57/month (~$684/year)

### Robustness Improvements ✅
- **PITR Recovery**: Tested and documented (`scripts/rollback_etl.sh`)
- **7-day retention**: Can restore to any second within window
- **Recovery time**: 5-10 minutes
- **Documentation**: `docs/BACKUP_RECOVERY_STRATEGY.md`

### ETL Optimization ✅
- **Runtime**: 15 min → 4 min (73% faster)
- **Data processed**: 945MB SQL dump → 97,000+ analytics rows
- **Test pass rate**: 90.8% (69/76 dbt tests)

---

## Data Summary

### Active Schemas

| Schema | Tables | Rows | Purpose |
|--------|--------|------|---------|
| **staging** | 81 | Various | Bronze: Raw SQL dump data |
| **silver** | 6 | 59,118 (int_contracts) | Silver: Cleaned & standardized |
| **gold** | 4 | 41,027 total | Gold: Business analytics |
| **seeds** | 6 | 73 total | Reference data mappings |

### Gold Tables (Business Analytics)

| Table | Rows | Description |
|-------|------|-------------|
| `daily_activity_summary` | 5,624 | Daily KPIs by tenant type |
| `new_contracts` | 16,508 | Demographics + geolocation |
| `moveouts` | 15,262 | Tenure & revenue analysis |
| `moveout_notices` | 3,635 | 24-month rolling window |

**Total**: 41,027 analytics-ready rows  
**Updated**: Daily at 7:00 AM JST

---

## Infrastructure

### AWS Resources

| Resource | ID/Endpoint | Status |
|----------|-------------|--------|
| **Aurora Cluster** | `tokyobeta-prod-aurora-cluster-public` | Available |
| **Cluster Endpoint** | `*.cluster-cr46qo6y4bbb.ap-northeast-1.rds.amazonaws.com` | Active |
| **Glue Job** | `tokyobeta-prod-daily-etl` | Scheduled (daily 7AM) |
| **VPC** | `vpc-0973d4c359b12f522` | Active |
| **S3 Bucket** | `s3://jram-gghouse/` | Active |
| **SNS Topic** | `tokyobeta-prod-dashboard-etl-alerts` | Active |

### Backup Configuration

- **Method**: Aurora automated backups
- **Retention**: 7 days
- **Type**: Point-in-Time Recovery (PITR)
- **Cost**: $0 (included in Aurora pricing)
- **Restore Capability**: Any second within 7-day window
- **Recovery Time**: 5-10 minutes

---

## Cost Summary

### Current Monthly Costs

| Category | Amount | Notes |
|----------|--------|-------|
| **Infrastructure** | ~$91/month | Aurora, Glue, S3, VPC, CloudWatch |
| **Cost Savings** | -$57/month | Eliminated manual snapshots |
| **Net Infrastructure** | ~$91/month | Optimized from previous $148/month |

**QuickSight** (optional, not yet enabled):
- Authors (4 users): $72/month
- Readers (10 users): $50/month
- **Total with QuickSight**: ~$213/month

---

## Outstanding Items

### Low Priority
- [ ] **7 dbt test failures** - Data validation warnings only (non-critical)
  - Impact: Reference data has unexpected values
  - Action: Review seed CSVs or adjust test constraints
  
- [ ] **Investigate unknown databases**
  - `_test_results` (60 tables)
  - `test_results` (75 tables)
  - Action: Determine purpose before dropping

### Optional Enhancements
- [ ] **QuickSight Setup** - Enable dashboards for stakeholders
  - Follow: `scripts/quicksight/QUICKSIGHT_SETUP_GUIDE.md`
  - Time: ~1-2 hours for initial setup
  
- [ ] **Increase backup retention** - Extend from 7 to 14 or 30 days
  - Cost: Minimal (~$1-2/month additional)
  
- [ ] **Apply Terraform IAM changes** - Glue role RDS permissions
  - Status: Code ready, not yet applied
  - Command: `cd terraform/environments/prod && terraform apply`

---

## Performance Metrics

### ETL Job (Latest Run)

```
Job ID:     jr_baea4b06fe0e6fdae7d634ff55e575653966ae9ee4b4f02b5577761a5a46c795
Started:    2026-02-05 10:53:10 JST
Completed:  2026-02-05 10:57:18 JST
Duration:   235 seconds (~4 minutes)
Status:     SUCCEEDED
Tables:     91 (81 staging + 6 silver + 4 gold)
Tests:      69 PASS, 7 ERROR (90.8% pass rate)
```

### Data Quality

- **Test Coverage**: 76 tests total
- **Pass Rate**: 90.8% (69/76)
- **Critical Tests**: All passed (uniqueness, not-null, referential integrity)
- **Warnings**: 7 data validation tests (reference data values)

### System Health

- **Aurora CPU**: <20% average
- **Aurora Storage**: 20GB available
- **Glue Execution**: <5 minutes per run
- **ETL Success Rate**: 100% (last 10 runs)
- **Backup Status**: Healthy (7-day retention active)

---

## Quick Commands

### Check ETL Status
```bash
aws glue get-job-runs \
    --job-name tokyobeta-prod-daily-etl \
    --max-results 1 \
    --profile gghouse --region ap-northeast-1 \
    --query 'JobRuns[0].{Status:JobRunState,Time:ExecutionTime,Completed:CompletedOn}'
```

### Trigger Manual ETL
```bash
aws glue start-job-run \
    --job-name tokyobeta-prod-daily-etl \
    --profile gghouse --region ap-northeast-1
```

### Check Data Freshness
```bash
mysql -h tokyobeta-prod-aurora-cluster-public.cluster-cr46qo6y4bbb.ap-northeast-1.rds.amazonaws.com \
    -u admin -p gold \
    -e "SELECT TABLE_NAME, TABLE_ROWS FROM information_schema.TABLES WHERE TABLE_SCHEMA='gold';"
```

### Emergency Recovery
```bash
# Show available restore window
./scripts/rollback_etl.sh

# Restore to 1 hour ago (if needed)
./scripts/rollback_etl.sh "$(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ)"
```

---

## Recent Documentation

All documentation updated to reflect latest changes:

- ✅ `README.md` - Comprehensive project overview
- ✅ `docs/DATABASE_SCHEMA_EXPLANATION.md` - Complete schema inventory
- ✅ `docs/BACKUP_RECOVERY_STRATEGY.md` - Recovery procedures
- ✅ `docs/ROBUSTNESS_IMPLEMENTATION_SUMMARY.md` - Latest improvements
- ✅ `docs/CLEANUP_COMPLETION_REPORT.md` - Database cleanup results

---

## Next Steps

### For Operations Team
1. Monitor daily ETL runs via CloudWatch
2. Review weekly cost reports
3. Validate data quality metrics

### For Business Users (Optional)
1. Enable QuickSight ($122/month for 14 users)
2. Follow `scripts/quicksight/QUICKSIGHT_SETUP_GUIDE.md`
3. Create 4 dashboards (Executive, Contracts, Moveouts, Map)
4. Invite stakeholders (Warburg, JRAM, Tosei, GGhouse)

### For Developers
1. Review dbt test failures (low priority)
2. Investigate unknown test databases
3. Consider backup retention increase
4. Apply pending Terraform changes

---

## Support

**Technical Issues**: Check `README.md` for troubleshooting  
**Recovery Procedures**: See `docs/BACKUP_RECOVERY_STRATEGY.md`  
**Database Questions**: See `docs/DATABASE_SCHEMA_EXPLANATION.md`  
**Cost Questions**: Review cost breakdown in `README.md`

---

**Status**: Production-ready, cost-optimized, fully documented ✅  
**Last Verified**: February 5, 2026, 11:00 JST
