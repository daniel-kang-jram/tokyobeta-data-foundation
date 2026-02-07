# Documentation Index

**Project**: TokyoBeta Data Consolidation  
**Last Updated**: February 7, 2026

---

## 📚 Core Documentation

### Implementation & Operations

| Document | Description | Status |
|----------|-------------|--------|
| **[ETL_IMPLEMENTATION.md](ETL_IMPLEMENTATION.md)** | Complete ETL pipeline implementation, 3-stage architecture, deployment history, fixes | ✅ Current |
| **[SCHEMA_CLEANUP.md](SCHEMA_CLEANUP.md)** | Database schema cleanup, backup management, retention policies | ✅ Current |
| **[TENANT_STATUS_TRACKING.md](TENANT_STATUS_TRACKING.md)** | SCD Type 2 status history, queries, use cases, dashboard ideas | ✅ Current |

### Troubleshooting & Quality

| Document | Description | Status |
|----------|-------------|--------|
| **[INVESTIGATIONS_AND_FIXES.md](INVESTIGATIONS_AND_FIXES.md)** | All major issues, root causes, solutions, lessons learned | ✅ Current |
| **[DATA_QUALITY_REPORT.md](DATA_QUALITY_REPORT.md)** | Data quality metrics, validation framework, monitoring | ✅ Current |
| **[LESOTHO_FLAG_INVESTIGATION.md](LESOTHO_FLAG_INVESTIGATION.md)** | Detailed nationality data investigation and analysis | 📋 Reference |

### Architecture & Design

| Document | Description | Status |
|----------|-------------|--------|
| **[ARCHITECTURE_DECISION.md](ARCHITECTURE_DECISION.md)** | ETL framework selection (Glue + dbt vs alternatives) | 📋 Reference |
| **[UPDATED_ARCHITECTURE.md](UPDATED_ARCHITECTURE.md)** | Current system architecture diagrams and components | ✅ Current |
| **[DATABASE_SCHEMA_EXPLANATION.md](DATABASE_SCHEMA_EXPLANATION.md)** | Schema design, table relationships, data flow | 📋 Reference |
| **[DATA_DICTIONARY.md](DATA_DICTIONARY.md)** | Field definitions, business logic, code mappings | 📋 Reference |

### Data Protection & Strategy

| Document | Description | Status |
|----------|-------------|--------|
| **[DATA_PRESERVATION_EXPLAINED.md](DATA_PRESERVATION_EXPLAINED.md)** | How historical data is preserved during transformations | 📋 Reference |
| **[DATA_PROTECTION_STRATEGY.md](DATA_PROTECTION_STRATEGY.md)** | Backup strategy, retention, disaster recovery | 📋 Reference |
| **[BACKUP_RECOVERY_STRATEGY.md](BACKUP_RECOVERY_STRATEGY.md)** | Detailed backup/recovery procedures | 📋 Reference |
| **[HISTORICAL_DATA_PRESERVATION.txt](HISTORICAL_DATA_PRESERVATION.txt)** | Historical data handling notes | 📋 Reference |

### Infrastructure & Security

| Document | Description | Status |
|----------|-------------|--------|
| **[SECURITY_MIGRATION_PLAN.md](SECURITY_MIGRATION_PLAN.md)** | Security architecture and migration plan | 📋 Reference |
| **[DMS_VENDOR_REQUIREMENTS.md](DMS_VENDOR_REQUIREMENTS.md)** | Vendor requirements and specifications | 📋 Reference |
| **[DUMP_GENERATION_ALTERNATIVES_STATUS.md](DUMP_GENERATION_ALTERNATIVES_STATUS.md)** | Alternative dump generation methods evaluation | 📋 Reference |

### Communication

| Document | Description | Status |
|----------|-------------|--------|
| **[NAZCA_EMAIL_DRAFT.md](NAZCA_EMAIL_DRAFT.md)** | Email draft for Nazca communication | 📧 Draft |

---

## 📊 Data Exports

Analysis data exports in TSV format:

| File | Description | Rows |
|------|-------------|------|
| `active_moveout_notices.tsv` | Currently active moveout notices | Variable |
| `current_residents_top1000.tsv` | Top 1000 current residents | 1,000 |
| `expected_moveouts.tsv` | Expected upcoming moveouts | Variable |
| `recent_moveouts_top1000.tsv` | Top 1000 recent moveouts | 1,000 |
| `nationality_distribution_full.tsv` | Complete nationality breakdown | ~200 |
| `tenants_missing_nationality.tsv` | Tenants needing nationality enrichment | Variable |
| `lesotho_flag_tenants_full_list.tsv` | Flagged records for review | 173 |

---

## 🗂️ Documentation Organization

### Consolidated Documents
The following documents are **consolidated summaries** that replace multiple older files:

1. **ETL_IMPLEMENTATION.md** - Replaces:
   - ETL_DEPLOYMENT_FINAL_STATUS.md
   - ETL_DEPLOYMENT_SUMMARY.md
   - ETL_REFACTORING_IMPLEMENTATION_SUMMARY.md
   - ETL_REFACTORING_PLAN.md
   - ETL_SUCCESS_SUMMARY.md
   - GLUE_ETL_FIX_SUMMARY.md
   - CLUSTER_CONSOLIDATION_COMPLETE.md
   - ROBUSTNESS_IMPLEMENTATION_SUMMARY.md

2. **SCHEMA_CLEANUP.md** - Replaces:
   - SCHEMA_CLEANUP_SUMMARY.md
   - AUTOMATED_CLEANUP_SUMMARY.txt
   - AUTOMATED_TABLE_CLEANUP.md
   - CLEANUP_COMPLETION_REPORT.md
   - IMPLEMENTATION_AUTOMATED_CLEANUP.md
   - STAGING_TABLE_CLEANUP_GUIDE.md
   - DROPPED_TABLES_20260205_123010.md
   - STAGING_ACTIVE_TABLES_*.md (multiple)
   - STAGING_TABLES_WITH_RECENT_ACTIVITY.txt

3. **INVESTIGATIONS_AND_FIXES.md** - Replaces:
   - INVESTIGATION_AND_FIX_SUMMARY_20260207.md
   - DAILY_ACTIVITY_SUMMARY_FIX.md
   - DAILY_ACTIVITY_SUMMARY_METRICS.md
   - DATA_VALIDATION_ASSESSMENT.md

4. **TENANT_STATUS_TRACKING.md** - Replaces:
   - TENANT_STATUS_ANALYSIS_20260207.md
   - TENANT_STATUS_HISTORY_DEPLOYMENT.md
   - TENANT_STATUS_HISTORY_IMPLEMENTATION.md
   - TENANT_STATUS_HISTORY_SUMMARY.txt
   - TENANT_STATUS_TRACKING_GUIDE.md

5. **DATA_QUALITY_REPORT.md** - Replaces:
   - NATIONALITY_DATA_QUALITY_REPORT.md
   - LLM_NATIONALITY_ENRICHMENT.md

---

## 🔍 Quick Reference

### Finding Information

**"How does the ETL work?"**  
→ Read [ETL_IMPLEMENTATION.md](ETL_IMPLEMENTATION.md)

**"What issues have we had?"**  
→ Read [INVESTIGATIONS_AND_FIXES.md](INVESTIGATIONS_AND_FIXES.md)

**"How do I query tenant status history?"**  
→ Read [TENANT_STATUS_TRACKING.md](TENANT_STATUS_TRACKING.md)

**"What's our data quality status?"**  
→ Read [DATA_QUALITY_REPORT.md](DATA_QUALITY_REPORT.md)

**"What's the overall architecture?"**  
→ Read [UPDATED_ARCHITECTURE.md](UPDATED_ARCHITECTURE.md)

**"What do these fields mean?"**  
→ Read [DATA_DICTIONARY.md](DATA_DICTIONARY.md)

---

## 📅 Review Schedule

| Document | Review Frequency | Next Review |
|----------|------------------|-------------|
| ETL_IMPLEMENTATION.md | After major changes | As needed |
| INVESTIGATIONS_AND_FIXES.md | Weekly | Feb 14, 2026 |
| DATA_QUALITY_REPORT.md | Weekly | Feb 14, 2026 |
| TENANT_STATUS_TRACKING.md | Monthly | Mar 7, 2026 |
| SCHEMA_CLEANUP.md | Monthly | Mar 7, 2026 |
| ARCHITECTURE_DECISION.md | Quarterly | May 1, 2026 |

---

## 🤝 Contributing

When adding new documentation:

1. **Update existing docs** rather than creating new ones
2. **Use clear headings** for easy navigation
3. **Include examples** where appropriate
4. **Update this README** with new document references
5. **Add to git** with descriptive commit message

---

## 📞 Contact

**Data Engineering Team**  
**Project Repository**: `/Users/danielkang/tokyobeta-data-consolidation`

---

**Legend**:
- ✅ Current - Actively maintained, up-to-date
- 📋 Reference - Stable, reference only
- 📧 Draft - Work in progress
- ⚠️ Deprecated - Replaced, kept for reference only
