# LLM Enrichment Cache Architecture

**Created:** 2026-02-10  
**Problem Solved:** Prevents re-enriching same tenants every day

---

## The Problem

### Before (Wasteful Design)

```
Day 1:
  staging_loader loads dump → staging.tenants (no llm_nationality)
  enricher enriches 2,001 tenants → sets staging.tenants.llm_nationality
  Cost: 2,001 API calls × $0.001 = $2

Day 2:
  staging_loader loads NEW dump → OVERWRITES staging.tenants
  All llm_nationality values LOST!
  enricher enriches SAME 2,001 tenants again
  Cost: 2,001 API calls × $0.001 = $2

Day 3-30:
  Repeat forever...
  Total cost: 2,001 × 30 days = 60,030 API calls = $60/month
```

**Problems:**
- ❌ Re-enriching same records daily (wasteful)
- ❌ $2/day = $60/month for same 2,001 tenants
- ❌ LLM predictions lost on every staging reload
- ❌ No way to track enrichment history

---

## The Solution: Persistent Cache Table

### New Design (Efficient)

```
Day 1:
  staging_loader loads dump → staging.tenants
  enricher checks cache → finds 0 cached
  enricher enriches 2,001 tenants
  enricher writes to staging.llm_enrichment_cache (PERSISTENT)
  Cost: 2,001 API calls × $0.001 = $2

Day 2:
  staging_loader loads NEW dump → OVERWRITES staging.tenants
  enricher checks cache → finds 2,001 ALREADY enriched
  enricher skips them (uses cache)
  enricher only processes NEW tenants (if any)
  Cost: 0-10 API calls (only new tenants) = ~$0.01

Day 3-30:
  Only new tenants enriched (typically 5-10/day)
  Total cost: ~50 API calls = $0.05/month
```

**Benefits:**
- ✅ Each tenant enriched only ONCE (unless name changes)
- ✅ $2 one-time + $0.05/month ongoing (vs $60/month)
- ✅ 99% cost reduction
- ✅ Enrichment history preserved
- ✅ Can track prediction confidence over time

---

## Cache Table Schema

```sql
CREATE TABLE staging.llm_enrichment_cache (
    tenant_id INT UNSIGNED NOT NULL,
    
    -- Name at time of enrichment (for change detection)
    full_name VARCHAR(191) NOT NULL,
    full_name_hash CHAR(64) NOT NULL,  -- SHA256 for quick lookup
    
    -- LLM predictions
    llm_nationality VARCHAR(191) NULL,
    llm_confidence DECIMAL(5,4) NULL,
    
    -- Future LLM fields (ready for expansion)
    llm_occupation VARCHAR(191) NULL,
    llm_occupation_confidence DECIMAL(5,4) NULL,
    llm_company_type VARCHAR(191) NULL,
    llm_company_type_confidence DECIMAL(5,4) NULL,
    
    -- Metadata
    enriched_at TIMESTAMP NOT NULL,
    model_version VARCHAR(100) NOT NULL,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    
    PRIMARY KEY (tenant_id),
    UNIQUE KEY uk_name_hash (full_name_hash),
    KEY idx_enriched_at (enriched_at),
    KEY idx_full_name (full_name(100))
);
```

**Key features:**
- `tenant_id` PRIMARY KEY - One record per tenant
- `full_name_hash` - Quick lookup to detect name changes
- Future-proof - Columns ready for occupation, company_type, etc.
- Audit trail - enriched_at, model_version, updated_at

---

## How It Works

### Enricher Logic (Updated)

```python
# Step 1: Get tenants needing enrichment
SELECT t.id, t.full_name, t.nationality
FROM staging.tenants t
LEFT JOIN staging.llm_enrichment_cache c ON t.id = c.tenant_id
WHERE (
    t.nationality = 'レソト'
    OR t.nationality IS NULL
    OR t.nationality = ''
)
AND (
    c.tenant_id IS NULL  -- Not in cache yet
    OR SHA2(t.full_name, 256) != c.full_name_hash  -- Name changed
)
LIMIT 2500;

# Step 2: Call Bedrock for predictions (only uncached)

# Step 3: Write to cache (UPSERT)
INSERT INTO staging.llm_enrichment_cache 
    (tenant_id, full_name, full_name_hash, llm_nationality, llm_confidence, enriched_at, model_version)
VALUES (?, ?, SHA2(?, 256), ?, ?, NOW(), 'claude-3-haiku-20240307')
ON DUPLICATE KEY UPDATE
    full_name = VALUES(full_name),
    full_name_hash = VALUES(full_name_hash),
    llm_nationality = VALUES(llm_nationality),
    llm_confidence = VALUES(llm_confidence),
    enriched_at = VALUES(enriched_at),
    model_version = VALUES(model_version);
```

### dbt Silver Layer (Updated)

```sql
-- stg_tenants.sql now joins with cache
SELECT
    t.id,
    t.full_name,
    t.nationality as original_nationality,
    
    -- Read from persistent cache (survives staging reloads)
    llm_cache.llm_nationality,
    llm_cache.llm_confidence,
    llm_cache.enriched_at as llm_enriched_at,
    
    -- Use LLM prediction in nationality fallback logic
    CASE
        WHEN t.nationality IS NOT NULL AND t.nationality != 'レソト'
        THEN t.nationality
        WHEN llm_cache.llm_nationality IS NOT NULL  -- From cache!
        THEN llm_cache.llm_nationality
        ELSE 'その他'
    END as nationality
    
FROM staging.tenants t
LEFT JOIN staging.llm_enrichment_cache llm_cache
    ON t.id = llm_cache.tenant_id
```

---

## Daily Flow (After Implementation)

### Day 1 (First Enrichment)
```
staging_loader:
  - Loads dump → staging.tenants (50,425 tenants)
  
enricher:
  - Checks cache: 0 cached
  - Identifies: 2,001 need enrichment
  - Calls Bedrock: 2,001 API calls
  - Writes to: staging.llm_enrichment_cache
  - Cost: $2

silver_transformer:
  - Joins staging.tenants + llm_enrichment_cache
  - Gets LLM predictions for 2,001 tenants
```

### Day 2 (Cache Hit!)
```
staging_loader:
  - Loads NEW dump → OVERWRITES staging.tenants
  - Cache table NOT touched (separate table)
  
enricher:
  - Checks cache: 2,001 cached ✅
  - Identifies: 0 new records (all cached)
  - Calls Bedrock: 0 API calls
  - Cost: $0

silver_transformer:
  - Joins with cache
  - Gets same LLM predictions (from cache)
```

### Day 30 (New Tenants Added)
```
staging_loader:
  - Loads dump with 50,525 tenants (+100 new)
  
enricher:
  - Checks cache: 2,001 cached
  - Identifies: 5 new tenants need enrichment
  - Calls Bedrock: 5 API calls
  - Writes 5 new records to cache
  - Cost: $0.005

silver_transformer:
  - Joins with cache
  - Gets predictions for 2,006 tenants (2,001 old + 5 new)
```

---

## Implementation Steps

### 1. Create Cache Table ✅
```sql
-- Already created!
staging.llm_enrichment_cache
```

### 2. Update enricher to use cache

Edit `glue/scripts/nationality_enricher.py`:

```python
def identify_tenants_needing_enrichment(self):
    """Get tenants needing enrichment (checking cache first)."""
    
    query = f"""
        SELECT 
            t.id,
            t.full_name,
            t.last_name,
            t.first_name,
            t.nationality,
            t.status
        FROM staging.tenants t
        LEFT JOIN staging.llm_enrichment_cache c 
            ON t.id = c.tenant_id
        WHERE (
            t.nationality = 'レソト'
            OR t.nationality IS NULL
            OR t.nationality = ''
        )
        AND (
            c.tenant_id IS NULL  -- Not cached yet
            OR SHA2(t.full_name, 256) != c.full_name_hash  -- Name changed
        )
        ORDER BY ...
        LIMIT {self.max_batch_size}
    """

def update_tenant_predictions(self, predictions):
    """Write predictions to cache table (UPSERT)."""
    
    for pred in predictions:
        cursor.execute("""
            INSERT INTO staging.llm_enrichment_cache
                (tenant_id, full_name, full_name_hash, 
                 llm_nationality, llm_confidence, 
                 enriched_at, model_version)
            VALUES (%s, %s, SHA2(%s, 256), %s, %s, NOW(), %s)
            ON DUPLICATE KEY UPDATE
                full_name = VALUES(full_name),
                full_name_hash = VALUES(full_name_hash),
                llm_nationality = VALUES(llm_nationality),
                llm_confidence = VALUES(llm_confidence),
                enriched_at = VALUES(enriched_at),
                model_version = VALUES(model_version)
        """, (
            pred['tenant_id'],
            pred['full_name'],
            pred['full_name'],
            pred['predicted_nationality'],
            pred['confidence'],
            self.BEDROCK_MODEL_ID
        ))
```

### 3. Update dbt model to read from cache ✅
```sql
-- Already updated!
-- stg_tenants.sql now joins with llm_enrichment_cache
```

### 4. Update dbt sources

Add to `dbt/models/staging/_sources.yml`:
```yaml
sources:
  - name: staging
    tables:
      - name: llm_enrichment_cache
        description: Persistent cache for LLM predictions
```

---

## Cost Comparison

### Without Cache (Current - Wasteful)
```
Daily cost: 2,001 tenants × $0.001 = $2/day
Monthly: $2 × 30 = $60/month
Yearly: $60 × 12 = $720/year
Total API calls/year: 730,365
```

### With Cache (Proposed - Efficient)
```
Initial: 2,001 tenants × $0.001 = $2 (one-time)
Daily: ~5 new tenants × $0.001 = $0.005/day
Monthly: $0.005 × 30 = $0.15/month
Yearly: $2 + ($0.15 × 12) = $3.80/year
Total API calls/year: 2,001 + (5 × 365) = 3,826

Savings: $720 - $3.80 = $716.20/year (99.5% reduction!)
```

---

## Benefits

### Cost Efficiency
- ✅ 99.5% cost reduction ($720 → $3.80/year)
- ✅ 99.5% fewer API calls (730K → 3.8K/year)
- ✅ Faster enrichment (only process new records)

### Data Quality
- ✅ Predictions preserved across staging reloads
- ✅ Enrichment history tracked (enriched_at timestamp)
- ✅ Can detect when names change (triggers re-enrichment)
- ✅ Model version tracked (useful for A/B testing)

### Future-Proof
- ✅ Ready for multiple LLM columns (occupation, company_type)
- ✅ Can cache any LLM prediction
- ✅ Can implement confidence thresholds
- ✅ Can track prediction accuracy over time

---

## Migration Plan

### Phase 1: Create Infrastructure ✅
- [x] Create `staging.llm_enrichment_cache` table
- [x] Update `stg_tenants.sql` to join with cache
- [ ] Add cache table to dbt sources

### Phase 2: Update Enricher Logic
- [ ] Modify `identify_tenants_needing_enrichment()` to check cache
- [ ] Modify `update_tenant_predictions()` to write to cache
- [ ] Add name change detection (SHA256 hash comparison)
- [ ] Test with dry_run=True

### Phase 3: Deploy & Test
- [ ] Upload updated enricher to S3
- [ ] Run manual enrichment to populate cache
- [ ] Verify cache populated correctly
- [ ] Run silver_transformer to test join
- [ ] Monitor tomorrow's automated ETL

### Phase 4: Validate
- [ ] Check Day 2 enrichment only processes new tenants (0-10 calls)
- [ ] Verify cost reduction
- [ ] Monitor for any cache misses

---

## Cache Management

### Check Cache Status
```sql
-- How many tenants cached?
SELECT COUNT(*) as cached_count 
FROM staging.llm_enrichment_cache;

-- Cache hit rate
SELECT 
    COUNT(DISTINCT t.id) as total_target_tenants,
    COUNT(DISTINCT c.tenant_id) as cached_tenants,
    ROUND(COUNT(DISTINCT c.tenant_id) * 100.0 / COUNT(DISTINCT t.id), 2) as cache_hit_rate
FROM staging.tenants t
LEFT JOIN staging.llm_enrichment_cache c ON t.id = c.tenant_id
WHERE t.nationality IS NULL OR t.nationality = '' OR t.nationality = 'レソト';

-- Recent enrichments
SELECT 
    DATE(enriched_at) as enrichment_date,
    COUNT(*) as tenants_enriched
FROM staging.llm_enrichment_cache
GROUP BY DATE(enriched_at)
ORDER BY enrichment_date DESC
LIMIT 30;
```

### Clear Cache (If Needed)
```sql
-- Clear all cache (forces re-enrichment)
TRUNCATE TABLE staging.llm_enrichment_cache;

-- Clear specific tenant (for re-enrichment)
DELETE FROM staging.llm_enrichment_cache WHERE tenant_id = 12345;

-- Clear low-confidence predictions (for re-enrichment)
DELETE FROM staging.llm_enrichment_cache WHERE llm_confidence < 0.7;
```

---

## Next Steps

### Immediate (Today)
- [x] Create cache table
- [x] Update stg_tenants.sql to join cache
- [ ] Kill current enrichment (writing to wrong place)
- [ ] Update enricher to write to cache
- [ ] Re-run enrichment with cache logic

### This Week
- [ ] Add dbt source for llm_enrichment_cache
- [ ] Test cache hit rate after Day 2
- [ ] Monitor cost savings

### Future Enhancements
- [ ] Add confidence threshold (only cache if confidence > 0.7)
- [ ] Add name change detection alerts
- [ ] Track prediction accuracy (manual review)
- [ ] Implement cache warming (pre-populate from existing data)

---

**Status:** Cache table created ✅  
**Next:** Update enricher logic to use cache instead of staging.tenants.llm_nationality
