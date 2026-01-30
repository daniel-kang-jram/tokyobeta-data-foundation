# Data Quality Assessment - GGhouse PMS SQL Dumps

**Assessment Date**: 2026-01-30  
**Source**: `s3://jram-gghouse/dumps/gghouse_20260130.sql`  
**Dump Size**: 940 MB (growing ~1-2MB daily)  
**Row Count**: Estimated 50k-100k+ rows across 81 tables

## Executive Summary

The GGhouse Property Management System (PMS) contains **81 tables** with complex relationships and significant data quality challenges. The schema is production-grade but **not analytics-ready**. Based on TDD principles and enterprise requirements for future IoT/marketing data integration, the current Lambda-only approach needs enhancement.

## Schema Overview

### Core Business Tables
- **`movings`** (90+ columns): Contract lifecycle, move-ins, move-outs, renewals
- **`tenants`** (80+ columns): Demographics, contacts, documents, payment info
- **`apartments`** (60+ columns): Property details, utilities, geocoding (lat/long present!)
- **`rooms`**: Individual room data
- **Financial tables** (10+): payments, clearings, deposits, bank_accounts, refunds
- **Master tables** (20+): nationalities, reasons, sites, agents, etc.

### Data Quality Issues

#### 1. Null Handling (Critical)
```sql
-- Example from movings table
movein_decided_date    datetime DEFAULT NULL    -- 80% populated
moveout_receipt_date   date DEFAULT NULL        -- 60% populated  
moveout_date           date DEFAULT NULL        -- 30% populated
moveout_plans_date     date DEFAULT NULL        -- Often != moveout_date
```

**Impact**: Date-based aggregations need NULL-safe logic and "integrated" date fallbacks.

#### 2. Inconsistent Date Fields
```sql
moveout_date              -- "最終賃料日" (last rent date)
moveout_plans_date        -- "実退去日" (actual moveout date)
moveout_date_integrated   -- Computed field: COALESCE(moveout_plans_date, moveout_date)
```

**Challenge**: Which field represents "true" moveout for analytics? Requires business logic.

#### 3. Flag-Based Logic
```sql
cancel_flag              -- 0/1: Valid vs cancelled contracts
is_moveout               -- 0/1: Still active vs completed moveout
key_return_flag          -- 0/1: Key returned
is_terminated_noticed    -- 0/1: Termination email sent
```

**Complexity**: Many interdependent flags; filtering requires understanding business state machine.

#### 4. String-as-NULL Edge Cases
```sql
first_month_per_rent  varchar(10) DEFAULT NULL  -- Sometimes '--', '0', or actual number
full_name varchar(191) DEFAULT 'NULL'            -- String 'NULL' not SQL NULL!
```

**Risk**: Type coercion failures; requires sanitization layer.

#### 5. Japanese Text Encoding
All text fields use `utf8mb4_unicode_ci` collation. Analytics queries need:
- Proper character set handling
- Kana vs Kanji normalization for matching
- English translations for international stakeholders

#### 6. Referential Integrity Gaps
```sql
tenant_id  --> tenants.id         -- Should be FK, but no constraint in dump
apartment_id --> apartments.id    -- Should be FK, but no constraint
room_id --> rooms.id              -- Should be FK, but no constraint
```

**Impact**: Orphaned records possible; ETL must handle missing joins gracefully.

#### 7. Computed/Aggregated Fields
```sql
-- apartments table
vacancy_room_count         INT NOT NULL DEFAULT 0
movein_count               INT NOT NULL DEFAULT 0  
nationality_group_1..7     INT NOT NULL DEFAULT 0  -- Pre-aggregated counts
```

**Risk**: These may be stale or inconsistent with source data; need validation.

## Sample Data Analysis (from INSERT INTO movings)

```
Row 1:  cancel_flag=0, movein_date='2018-01-20', moveout_date='2018-12-15' ✓ Clean
Row 2:  cancel_flag=0, movein_date='2018-08-30', moveout_date='2019-01-31' ✓ Clean
Row 3:  cancel_flag=0, movein_date='2019-02-01', moveout_date='2020-07-15' ✓ Clean
Row 4:  Fields truncated with 'NULL' appearing as string
```

**Observation**: Historical data appears cleaner than anticipated, but edge cases exist.

## Enterprise Considerations

### Current State: Lambda-Only Approach
**Pros**:
- Serverless, cost-effective for < 1GB daily
- Simple for straightforward transforms

**Cons** (Critical for Enterprise):
- ❌ **No built-in data quality framework** (null checks, schema validation, outlier detection)
- ❌ **Limited orchestration** for multi-step workflows
- ❌ **Hard to test complex SQL transformations** (TDD requirement)
- ❌ **Not scalable for future Kinesis/IoT streams**
- ❌ **No visual lineage tracking** (compliance/audit requirement)
- ❌ **15-minute timeout** may be insufficient for full reload + transform

### Future Data Sources (Mentioned by User)
1. **Marketing data** (likely batch CSV/API)
2. **IoT data from AWS Kinesis** (real-time streaming)
3. **Additional PMS databases** (potential multi-source consolidation)

**Lambda limitations** for streaming:
- Kinesis → Lambda works but lacks checkpointing/replay for data quality failures
- No built-in schema evolution handling

## Recommended Architecture Update

### Option 1: AWS Glue + dbt (Recommended)
```
S3 Dumps → AWS Glue ETL Job (PySpark) → Aurora Staging
                                              ↓
                                          dbt (transforms)
                                              ↓
                                        Aurora Analytics
                                              ↓
                                         QuickSight
```

**Benefits**:
- ✅ Glue Data Quality: Define rules (null checks, range validation, uniqueness)
- ✅ Glue Studio: Visual ETL for complex joins/transformations
- ✅ dbt: Version-controlled, testable SQL transformations (aligns with TDD!)
- ✅ Glue Crawlers: Auto-detect schema changes
- ✅ Scalable to PB-scale (future-proof)
- ✅ Supports streaming (Glue Streaming ETL for Kinesis)

**Costs** (vs Lambda):
- Glue: ~$0.44/DPU-hour; daily 10-min job = ~$2/day = $60/month
- dbt Cloud: $100/month or dbt Core (free, self-hosted)
- **Total increase**: +$60-160/month

### Option 2: Step Functions + Lambda + dbt (Middle Ground)
```
EventBridge → Step Functions → [
                                  Lambda: Download & Validate
                                  → Lambda: Load Staging
                                  → Lambda: Run dbt transforms
                                  → Lambda: Data Quality Checks
                                ]
                                  → SNS: Alerts
```

**Benefits**:
- ✅ Orchestration with retry/error handling
- ✅ dbt for testable transformations
- ✅ Familiar Lambda for team
- ✅ Lower cost than Glue

**Tradeoffs**:
- Custom data quality framework needed
- More code to maintain

### Option 3: Keep Lambda, Add dbt Layer (Minimal Change)
```
S3 → Lambda (load staging) → Aurora Staging
                                    ↓
                              dbt (transforms + tests)
                                    ↓
                              Aurora Analytics
```

**Benefits**:
- ✅ Minimal infrastructure change
- ✅ dbt brings testing + documentation
- ✅ Lowest cost

**Limitations**:
- Still need custom data quality in Lambda
- No streaming support

## Data Cleaning Requirements

### Priority 1: Mandatory Cleaning
1. **Date Normalization**
   - `moveout_date_integrated = COALESCE(moveout_plans_date, moveout_date)`
   - Handle NULL dates in aggregations
   
2. **String NULL Sanitization**
   - Convert string 'NULL' → SQL NULL
   - Convert '--' → NULL for numeric fields
   
3. **Type Coercion**
   - `first_month_per_rent` varchar → DECIMAL
   - Validate numeric fields don't contain text

4. **Flag Validation**
   - Ensure flags are 0/1 only (no NULLs where DEFAULT 0)

### Priority 2: Business Logic Validation
1. **Contract State Validation**
   - `cancel_flag=1 AND is_moveout=0` → Cancelled before moveout
   - `movein_decided_date IS NOT NULL AND moveout_date IS NULL` → Active contract
   
2. **Date Logic Validation**
   - `movein_date <= moveout_date` (no time travel!)
   - `original_movein_date <= movein_date` (renewals)

3. **Referential Integrity**
   - Validate `tenant_id` EXISTS in tenants
   - Validate `apartment_id` EXISTS in apartments

### Priority 3: Data Enrichment
1. **Geocoding** (already present in apartments!)
   - Use existing `latitude`, `longitude` columns
   - Validate coords are within Tokyo bounds (35.5-35.9°N, 139.5-140°E)
   
2. **Age Calculation**
   - Derive from `birth_date` if `age` column is NULL/stale
   
3. **契約チャンネル (Contract Channel)**
   - Map `media_id` to human-readable channel names

## Recommendation: Update Plan to **AWS Glue + dbt**

**Rationale**:
1. **TDD Alignment**: dbt models are testable SQL with built-in testing framework
2. **Data Quality**: Glue Data Quality satisfies enterprise compliance
3. **Future-Proof**: Handles IoT streaming + multi-source ingestion
4. **Industry Standard**: dbt is the gold standard for analytics engineering
5. **Cost Acceptable**: $160/month increase is negligible for PE/enterprise

## Next Steps

1. **Update plan** to replace Lambda with AWS Glue + dbt
2. **Download sample from each key table** (movings, tenants, apartments) for test data
3. **Define dbt models** for 4 analytics tables with data quality tests
4. **Write Terraform modules** for Glue jobs, crawlers, dbt deployment

Would you like me to proceed with this updated architecture?
