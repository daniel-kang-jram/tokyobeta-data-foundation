# LLM Enrichment Architecture

**Last Updated:** 2026-02-10

## Current Implementation

### How It Works

The LLM enricher is **NOT a separate Glue job**. It's embedded inside the `staging_loader` job:

```
EventBridge (7 AM JST)
    ↓
staging_loader.py
    ↓
  1. Download SQL dump from S3
  2. Load to staging.* tables
  3. ⭐ Call enrich_nationality_data() ← EMBEDDED HERE
  4. Trigger silver_transformer
```

### Code Flow

In `glue/scripts/staging_loader.py`:

```python
def main():
    # ... load data to staging ...
    
    # Step 5: LLM enrichment (non-critical, can fail)
    try:
        enriched_count = enrich_nationality_data()
    except Exception as e:
        print(f"Warning: Enrichment failed: {e}")
        # Continue anyway - enrichment is optional
    
    # Step 6: Trigger silver transformer
    trigger_silver_transformer()
```

**Key points:**
- Runs **automatically** as part of daily ETL (7 AM JST)
- Processes up to **1,000 tenants per day** (batch limit)
- **Non-critical** - if it fails, ETL continues
- Uses **AWS Bedrock** (Claude) for predictions
- Rate limited to 5 requests/second

### Current Status (Feb 10, 2026)

**Problem:** staging_loader hasn't run since we manually loaded data today.

**Target records needing enrichment:**
- Total tenants: 50,425
- NULL nationality: 654
- Empty nationality (''):  545
- レソト placeholder: 802
- **Total needing enrichment: 2,001** (~4% of tenants)

**Result:**
- `llm_nationality` column doesn't exist in `staging.tenants`
- No enrichment has run yet
- 0 of 2,001 target records enriched (0%)

### Tomorrow (Feb 11, 2026)

**7:00 AM JST:** EventBridge triggers staging_loader:
1. Loads gghouse_20260211.sql
2. Automatically runs enrichment (up to 1,000 tenants per day)
3. Updates `staging.tenants.llm_nationality`
4. Triggers silver_transformer (which now handles missing column gracefully)

**Expected enrichment:**
- **Target records:** 2,001 tenants (4% of total)
  - NULL: 654
  - Empty: 545
  - レソト: 802
- **Day 1 (Feb 11):** Enriches ALL 2,001 records (100% complete)
- **Day 2+ onwards:** Finds 0 records (all already enriched) ✅
- **Total time:** 1 day to complete all enrichment
- Prioritizes active residents first (status 9, 11, 14, 15, 16)
- **Updated:** max_batch_size increased from 1,000 to 2,500

---

## Renaming to llm_enricher (Future)

### Why Rename?

Current name: `nationality_enricher.py`  
Problem: Too specific - will add other LLM columns in future

**Future columns:**
- `llm_occupation` (from name + context)
- `llm_company_type` (from affiliation name)
- `llm_income_estimate` (from occupation + demographics)
- etc.

### Renaming Plan

1. **Rename files:**
   ```bash
   mv glue/scripts/nationality_enricher.py glue/scripts/llm_enricher.py
   mv glue/tests/test_nationality_enricher.py glue/tests/test_llm_enricher.py
   ```

2. **Update imports in:**
   - `glue/scripts/staging_loader.py`
   - `glue/scripts/daily_etl.py`
   - Any other scripts importing it

3. **Refactor class:**
   ```python
   # Old
   class NationalityEnricher:
       def enrich_all_missing_nationalities():
   
   # New
   class LLMEnricher:
       def enrich_nationality():  # Specific method
       def enrich_occupation():   # New method
       def enrich_company_type():  # New method
   ```

4. **Update S3 paths:**
   ```bash
   aws s3 mv \
     s3://jram-gghouse/glue-scripts/nationality_enricher.py \
     s3://jram-gghouse/glue-scripts/llm_enricher.py \
     --profile gghouse
   ```

5. **Update staging_loader.py:**
   ```python
   # Old
   s3.download_file(bucket, 'glue-scripts/nationality_enricher.py', path)
   from nationality_enricher import NationalityEnricher
   enricher = NationalityEnricher(...)
   
   # New
   s3.download_file(bucket, 'glue-scripts/llm_enricher.py', path)
   from llm_enricher import LLMEnricher
   enricher = LLMEnricher(...)
   enricher.enrich_nationality()
   # enricher.enrich_occupation()  # Future
   ```

---

## Configuration

### Current Settings (in staging_loader.py)

```python
enricher = NationalityEnricher(
    aurora_endpoint=args['AURORA_ENDPOINT'],
    aurora_database=args['AURORA_DATABASE'],
    secret_arn=args['AURORA_SECRET_ARN'],
    bedrock_region='us-east-1',
    max_batch_size=1000,  # Process up to 1000 per day
    requests_per_second=5,  # Rate limit for Bedrock API
    dry_run=False
)
```

### Tuning Parameters

**max_batch_size:**
- Current: 1,000 tenants/day
- Time to complete: ~50 days for 50K tenants
- Can increase to 2,000-5,000 if needed
- Cost: ~$0.001 per tenant (Bedrock Claude)

**requests_per_second:**
- Current: 5 requests/second
- Bedrock limits: 10,000 requests/minute
- Can increase to 10-20 if needed

**Estimated cost:**
- 50,425 tenants × $0.001 = ~$50 total
- 1,000/day × 50 days = $1/day

---

## Disabling Enrichment (If Needed)

### Option 1: Comment out in staging_loader.py

```python
def main():
    # ... load data ...
    
    # # Step 5: LLM enrichment
    # enriched_count = enrich_nationality_data()
    
    # Step 6: Trigger silver
    trigger_silver_transformer()
```

### Option 2: Set dry_run=True

```python
enricher = NationalityEnricher(
    # ...
    dry_run=True  # Won't actually update database
)
```

### Option 3: Set max_batch_size=0

```python
enricher = NationalityEnricher(
    # ...
    max_batch_size=0  # Won't process any tenants
)
```

---

## Monitoring

### Check Enrichment Progress

```sql
-- How many tenants have been enriched?
SELECT 
    COUNT(*) as total_tenants,
    COUNT(llm_nationality) as enriched_count,
    ROUND(COUNT(llm_nationality) * 100.0 / COUNT(*), 2) as enrichment_pct
FROM staging.tenants;

-- Which nationalities were predicted?
SELECT 
    llm_nationality,
    COUNT(*) as count
FROM staging.tenants
WHERE llm_nationality IS NOT NULL
GROUP BY llm_nationality
ORDER BY count DESC
LIMIT 20;

-- Check prediction quality (compare with original)
SELECT 
    nationality as original,
    llm_nationality as predicted,
    COUNT(*) as count
FROM staging.tenants
WHERE llm_nationality IS NOT NULL
    AND nationality IS NOT NULL
    AND nationality != llm_nationality
GROUP BY nationality, llm_nationality
ORDER BY count DESC
LIMIT 20;
```

### CloudWatch Logs

Check `/aws-glue/jobs/output` for staging_loader logs:
```
✓ Nationality enrichment completed:
  - Tenants identified: 1000
  - Predictions made: 1000
  - Successful updates: 1000
  - Failed updates: 0
  - Execution time: 180.5s
```

---

## Future Enhancements

### 1. Multiple LLM Columns

**Schema changes needed:**
```sql
ALTER TABLE staging.tenants
ADD COLUMN llm_occupation VARCHAR(191) NULL,
ADD COLUMN llm_occupation_confidence DECIMAL(5,4) NULL,
ADD COLUMN llm_company_type VARCHAR(191) NULL,
ADD COLUMN llm_company_type_confidence DECIMAL(5,4) NULL;
```

**Enricher refactoring:**
```python
class LLMEnricher:
    def enrich_nationality(self, batch_size=1000):
        """Enrich nationality from tenant name."""
        
    def enrich_occupation(self, batch_size=1000):
        """Enrich occupation from name + affiliation."""
        
    def enrich_company_type(self, batch_size=1000):
        """Enrich company type from affiliation name."""
        
    def enrich_all(self):
        """Run all enrichment types."""
        self.enrich_nationality()
        self.enrich_occupation()
        self.enrich_company_type()
```

### 2. Batch Processing Optimization

Currently processes tenants one-by-one. Could batch to Bedrock:
```python
# Current (slow)
for tenant in tenants:
    prediction = bedrock.invoke(tenant.name)
    
# Future (fast)
batch = [t.name for t in tenants[:100]]
predictions = bedrock.invoke_batch(batch)  # 100 at once
```

### 3. Caching / Memoization

Common names could be cached:
```python
# Cache predictions for common names
name_cache = {
    "田中 太郎": {"nationality": "日本", "confidence": 0.95},
    "李 明": {"nationality": "中国", "confidence": 0.90},
}
```

### 4. Incremental Enrichment

Only enrich new tenants (not re-process existing):
```sql
SELECT * FROM staging.tenants 
WHERE llm_nationality IS NULL
    AND created_at >= DATE_SUB(CURRENT_DATE, INTERVAL 7 DAY)
```

---

## See Also

- `glue/scripts/nationality_enricher.py` - Current enricher implementation
- `glue/scripts/staging_loader.py` - Where enricher is called
- `glue/tests/test_nationality_enricher.py` - Unit tests
- `dbt/models/silver/stg_tenants.sql` - Consumes llm_nationality
