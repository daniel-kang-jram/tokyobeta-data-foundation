# Architecture Decision: ETL Framework Selection

## Context

After analyzing the actual S3 dump data from `s3://jram-gghouse/dumps/`, we discovered:

- **81 tables** with complex relationships
- **900MB+ dumps** growing 1-2MB daily
- **Significant data quality issues**: NULL handling, string 'NULL' vs SQL NULL, date inconsistencies
- **Future requirements**: Marketing data, IoT/Kinesis streams, multi-source consolidation
- **Enterprise stakeholders**: Warburg (PE), JRAM, Tosei, GGhouse
- **TDD Requirement** from .cursorrules: All code must be testable with ≥80% coverage

## The Problem with Lambda-Only Approach

| Requirement | Lambda | Assessment |
|------------|--------|------------|
| Data Quality Framework | ❌ None built-in | Must write custom validation |
| Testing (TDD) | ⚠️ Hard to test SQL | Python tests, but SQL transforms untested |
| Complex Transformations | ⚠️ Code-heavy | 81 tables → 4 analytics tables = complex logic |
| Orchestration | ❌ Basic | No retry, dependencies, or checkpointing |
| Streaming (Kinesis) | ⚠️ Limited | Works but no schema evolution handling |
| Lineage Tracking | ❌ None | Compliance/audit gap |
| 15-min timeout | ⚠️ Risk | 900MB dump + transforms may exceed |
| Cost | ✅ $5/month | Very low |

## Three Options for Decision

### Option 1: AWS Glue + dbt (RECOMMENDED)

**Architecture**:
```
S3 Dumps → AWS Glue ETL (PySpark)  
              → Aurora Staging (raw reload)  
                  → dbt Cloud/Core (transformations + tests)  
                      → Aurora Analytics (4 tables)  
                          → QuickSight
```

**Components**:
- **AWS Glue**: Data catalog, ETL jobs, data quality rules, crawlers
- **dbt**: SQL-based transformations with built-in testing (✅ TDD!)
- **Glue Data Quality**: Define rules for NULL checks, range validation, referential integrity
- **Glue Streaming**: Future Kinesis integration ready

**Pros**:
- ✅ **TDD-Compliant**: dbt has built-in test framework (`dbt test`)
- ✅ **Data Quality**: Glue DQ rules validate data before loading
- ✅ **Visual ETL**: Glue Studio for complex joins (non-technical stakeholders can review)
- ✅ **Streaming-Ready**: Glue Streaming ETL for Kinesis
- ✅ **Schema Evolution**: Glue Crawlers auto-detect changes
- ✅ **Lineage**: AWS Glue Data Catalog tracks lineage
- ✅ **Scalable**: Handles PB-scale (future-proof)

**Cons**:
- ⚠️ **Cost**: ~$60-80/month for daily Glue jobs + $100/month for dbt Cloud (or free dbt Core)
- ⚠️ **Complexity**: More components to manage
- ⚠️ **Learning Curve**: Team needs to learn dbt (but it's industry standard)

**Cost Estimate**:
- Glue ETL: $0.44/DPU-hour × 2 DPU × 0.17 hours/day × 30 days = ~$4.50/month (optimistic)
- Glue ETL realistic: ~$60/month (with retries, dev testing)
- dbt Cloud: $100/month (Developer tier) or $0 (dbt Core self-hosted)
- **Total Increase**: +$60-160/month → **New total**: $285-385/month

### Option 2: Step Functions + Lambda + dbt Core (MIDDLE GROUND)

**Architecture**:
```
EventBridge → Step Functions  
                 ↓
           [Parallel Steps]
             Lambda 1: Download & Validate S3 dump
             Lambda 2: Load to Staging
             Lambda 3: Run dbt transformations
             Lambda 4: Data Quality Checks
                 ↓
           SNS: Success/Failure Alerts
```

**Components**:
- **Step Functions**: Orchestrate multi-Lambda workflow with retry logic
- **Lambda**: Handle S3 download, staging load, trigger dbt
- **dbt Core**: Run transformations (free, self-hosted)
- **Custom Data Quality**: Python scripts in Lambda

**Pros**:
- ✅ **TDD-Compliant**: dbt tests + Lambda unit tests
- ✅ **Cost-Effective**: $15-20/month (Step Functions + Lambda)
- ✅ **Familiar**: Team already knows Lambda
- ✅ **Flexible**: Full Python control for custom logic

**Cons**:
- ⚠️ **Manual DQ Framework**: Must build data quality rules from scratch
- ⚠️ **No Visual ETL**: Harder for non-technical stakeholders
- ⚠️ **Kinesis Integration**: Requires separate Lambda + Kinesis setup

**Cost Estimate**:
- Step Functions: $0.025/1000 transitions × 30 days × 5 steps = ~$0.04/month
- Lambda: ~$10/month (longer execution for dbt)
- dbt Core: $0 (self-hosted)
- **Total Increase**: +$10/month → **New total**: $235/month

### Option 3: Enhanced Lambda + dbt Core (MINIMAL CHANGE)

**Architecture**:
```
EventBridge → Lambda (all-in-one)
                ↓
           [Sequential in single Lambda]
             1. Download S3 dump (streaming)
             2. Load to Staging (chunks)
             3. Run dbt transformations
             4. Custom data quality checks
                ↓
           SNS: Alerts
```

**Components**:
- **Single Lambda** (1024MB, 15-min timeout)
- **dbt Core**: Transformations + tests
- **Custom Python**: Data quality validation

**Pros**:
- ✅ **TDD-Compliant**: dbt tests + Lambda unit tests
- ✅ **Lowest Cost**: ~$10/month total
- ✅ **Simplest**: Fewest moving parts
- ✅ **Fast Deployment**: Minimal infrastructure

**Cons**:
- ❌ **Timeout Risk**: 900MB dump + transforms may exceed 15 min
- ❌ **No Retry Logic**: If any step fails, restart from beginning
- ❌ **Memory Constraints**: 10GB max Lambda memory
- ❌ **No Streaming Support**: Cannot handle Kinesis

**Cost Estimate**:
- Lambda: ~$10/month
- dbt Core: $0
- **Total Increase**: +$5/month → **New total**: $230/month

## Recommendation Matrix

| Criterion | Option 1 (Glue+dbt) | Option 2 (Step+dbt) | Option 3 (Lambda+dbt) |
|-----------|---------------------|---------------------|------------------------|
| TDD Compliance | ✅ Excellent | ✅ Good | ✅ Good |
| Data Quality | ✅ Built-in (Glue DQ) | ⚠️ Custom | ⚠️ Custom |
| Cost | ⚠️ $285-385/mo | ✅ $235/mo | ✅ $230/mo |
| Future Kinesis | ✅ Native support | ⚠️ Custom | ❌ Not suitable |
| Enterprise-Grade | ✅ Yes | ⚠️ Partial | ❌ No |
| Complexity | ⚠️ High | ⚠️ Medium | ✅ Low |
| PE/Audit Compliance | ✅ Lineage tracking | ⚠️ Manual | ❌ Minimal |

## Decision Needed

Given:
1. Enterprise stakeholders (Warburg PE firm) → likely audit/compliance requirements
2. Future IoT/Kinesis data → need streaming capability
3. Dirty data (81 tables) → need robust data quality
4. TDD requirement → need testable transformations

**My recommendation: Option 1 (AWS Glue + dbt)**

**Budget-conscious alternative: Option 2 (Step Functions + Lambda + dbt Core)**

**If speed-to-market is priority: Option 3, with plan to migrate to Option 1 later**

## Questions for User

1. Is the +$60-160/month cost acceptable for enterprise-grade data quality?
2. How critical is Kinesis/streaming support for near-term (next 6 months)?
3. Are there audit/compliance requirements from Warburg/Tosei that require lineage tracking?
4. Would the team be comfortable learning dbt (2-week ramp-up)?

## Next Actions

**If Option 1 (Glue + dbt)**:
- Update plan to replace Lambda module with Glue module
- Add dbt project structure (`models/`, `tests/`, `dbt_project.yml`)
- Define Glue Data Quality rulesets for 4 analytics tables

**If Option 2 (Step Functions)**:
- Add Step Functions module to Terraform
- Break Lambda into 4 separate functions
- Add dbt Core deployment to Lambda layer

**If Option 3 (Keep Lambda)**:
- Increase Lambda memory to 2048MB, timeout to 900s (15 min)
- Add dbt Core to Lambda deployment package
- Implement custom data quality framework
