# 🚨 CRITICAL: レソト (Lesotho) Used as Data Quality Placeholder Flag

**Investigation Date:** 2026-02-07  
**Investigator:** Data Quality Team  
**Status:** ⚠️ **CONFIRMED DATA ISSUE**

---

## Executive Summary

**Finding:** The nationality "レソト" (Lesotho, m_nationality_id=200) is being used as a **placeholder flag** for tenant records with incomplete demographic data. This is **NOT real nationality data**.

### Key Evidence

| Metric | Value | Significance |
|--------|-------|--------------|
| Total レソト records | 683 | 1.42% of all tenants |
| Creation period | Sept-Oct 2025 | Bulk import event |
| Missing affiliation | 683 (100%) | Systematic NULL pattern |
| Missing gender | 683 (100%) | Systematic NULL pattern |
| Missing birth_date | 1 (0.15%) | Nearly complete |
| Actual Lesotho residents expected | ~0 | Lesotho is a small African country |

### Observed Tenant Names (Not from Lesotho!)

```
SAW THANDAR (Myanmar)
BKRASHMINA (South Asian)
YUHUIMIN (Chinese)
DAVAADELEG BYAMBASUREN (Mongolian)
Chechetkina Ekaterina (Russian)
AndreiDubovskoi (Russian)
LIU YANLIN (Chinese)
Shohei Sakai (Japanese)
蔡欣芸 (Chinese)
홍혜진 (Korean)
张 钰晨 (Chinese)
西 将司 (Japanese)
... (683 total records)
```

**These names clearly represent diverse nationalities, NOT Lesotho.**

---

## 1. Detailed Analysis

### 1.1 Data Distribution

**Staging Layer:**
- Total レソト records: **683**
- Percentage of all tenants: **1.42%**
- Nationality ID: **200**
- Nationality Group ID: **0** (Miscellaneous/Other)

**Silver Layer:**
- `stg_tenants`: **683** records
- `int_contracts`: **121** contracts (120 distinct tenants)

**Gold Layer:**
- `new_contracts`: **0** records ✅
- `moveouts`: **0** records ✅
- `moveout_notices`: **0** records ✅

**Good news:** Gold layer transformations successfully filter out these placeholder records.

### 1.2 Tenant Status Breakdown

| Status Code | Status Label | Count | Percentage |
|-------------|--------------|-------|------------|
| 9 | In Residence | 563 | 82.4% |
| 16 | Awaiting Maintenance | 92 | 13.5% |
| 8 | Canceled | 15 | 2.2% |
| 17 | Moved Out | 6 | 0.9% |
| 15 | Expected Move-out | 3 | 0.4% |
| 14 | Move-out Notice Received | 2 | 0.3% |
| 11 | Move-in Notice Received | 2 | 0.3% |

**Critical:** 563 tenants (82.4%) are currently "In Residence" with incorrect nationality data.

### 1.3 Creation Timeline

All 683 records were created in a **2-month window** during Sept-Oct 2025:

| Month | Records Created | % of Month's Tenants |
|-------|----------------|----------------------|
| 2025-09 | 531 | 8.29% |
| 2025-10 | 152 | 8.94% |
| **Total** | **683** | **8.43%** |

This represents a **bulk data import or migration event** where:
1. Source system had incomplete nationality data
2. Default nationality was set to "レソト" (ID=200)
3. Other demographic fields (gender, affiliation) systematically set to NULL

### 1.4 Data Completeness Comparison

Comparing レソト vs normal tenants created in the same period (Sept-Oct 2025):

| Field | レソト Tenants Missing | Normal Tenants Missing |
|-------|----------------------|------------------------|
| Affiliation | **683 (100%)** ⚠️ | 6,842 (92%) |
| Gender | **683 (100%)** ⚠️ | 5,588 (75%) |
| Birth Date | 1 (0.15%) | 0 (0%) |

**Pattern:** レソト flag correlates with **100% missing** gender and affiliation data.

### 1.5 Tenant ID Range

| Metric | Value |
|--------|-------|
| Minimum tenant_id | 87,306 |
| Maximum tenant_id | 96,607 |
| Distinct statuses | 7 |

The tenant IDs cluster in a specific range, further confirming this was a batch import event.

---

## 2. Root Cause Analysis

### 2.1 Most Likely Scenario: Data Migration Issue

**Timeline:** September 14-15, 2025

**What Happened:**
1. GGHouse system underwent a data migration or bulk import
2. Source data lacked nationality information for ~683 tenant records
3. System defaulted to nationality_id = 200 ("レソト") as a placeholder
4. Gender and affiliation fields were also systematically set to NULL
5. Records were successfully imported into staging database

**Why レソト?**
- Lesotho (ID=200) is at the end of the nationality lookup table
- May have been used as a "default/unknown" flag by the migration script
- Unlikely to conflict with real tenant data (no real Lesotho residents expected)

### 2.2 Alternative Hypotheses (Less Likely)

**Hypothesis A: Application Bug**
- New feature rolled out in September 2025
- Default nationality incorrectly set to "レソト" instead of NULL
- **Evidence against:** All records created in 2-month window only, then stopped

**Hypothesis B: Manual Data Entry Error**
- Batch of tenant records manually entered with wrong nationality
- **Evidence against:** Too many records (683), systematic NULL pattern in other fields

**Hypothesis C: Integration with External System**
- New integration with property management system
- レソト used as "pending verification" flag
- **Evidence against:** No evidence of ongoing usage after October 2025

---

## 3. Business Impact

### 3.1 Current Impact

✅ **Low impact on analytics (gold layer):**
- Gold tables successfully filter out these records
- QuickSight dashboards show accurate nationality distributions
- No data corruption in final reports

⚠️ **Medium impact on operations:**
- 563 active residents have incorrect nationality in staging/silver
- Data entry staff may be confused by "Lesotho" labels
- Manual queries on staging/silver layers show inflated Lesotho numbers

🔴 **High impact on data quality perception:**
- 1.42% of tenant records flagged as data quality issues
- Undermines trust in nationality reporting
- Requires constant explanation to stakeholders

### 3.2 Financial Impact

**None identified.** This is a data quality issue, not a billing or contract issue.

### 3.3 Compliance Impact

**Potential risk:**
- If nationality data is required for compliance reporting (visa tracking, etc.)
- 563 active residents have incorrect nationality on record
- May need correction for government reporting or audits

---

## 4. Recommendations

### Priority 1: IMMEDIATE - Data Cleanup (This Week)

#### 4.1 Identify True Nationalities

**Action:** Review tenant contracts and source documents for the 563 active residents

**SQL Query to Generate Review Queue:**
```sql
-- Active residents with レソト flag (prioritize for review)
SELECT 
    t.id as tenant_id,
    t.full_name,
    t.nationality as current_nationality_flag,
    t.contact_nationality_1 as alternate_nationality,
    t.status as status_code,
    ts.label_en as status_label,
    m.contract_date,
    m.apartment_id,
    t.created_at
FROM staging.tenants t
LEFT JOIN seeds.code_tenant_status ts ON t.status = ts.code
LEFT JOIN staging.movings m ON t.id = m.tenant_id
WHERE t.nationality = 'レソト'
  AND t.status IN (9, 11, 14, 15, 16) -- Active or pending statuses
ORDER BY m.contract_date DESC;
```

**Expected Effort:** 
- ~15 minutes per record for manual review
- 563 active records × 15 min = **~140 hours**
- Recommend: 2 data entry staff, 1 week at 4 hours/day

#### 4.2 Bulk Update Strategy

**Option A: Contact Nationality Field**
```sql
-- Check if contact_nationality_1 field has usable data
SELECT 
    contact_nationality_1,
    COUNT(*) as count
FROM staging.tenants
WHERE nationality = 'レソト'
  AND contact_nationality_1 IS NOT NULL
GROUP BY contact_nationality_1;
```

**Option B: Name-Based Nationality Prediction**
```sql
-- Use name patterns to predict nationality (requires validation)
-- Example: Names in Kanji (Chinese chars) → likely Japanese, Chinese, or Korean
-- Requires manual verification before applying
```

**Option C: Manual Review Queue**
- Export TSV file (already created: `lesotho_flag_tenants_full_list.tsv`)
- Distribute to data entry team with source documents
- Update records individually via GGHouse application

### Priority 2: SHORT-TERM - Prevent Future Issues (Next 2 Weeks)

#### 4.3 Add Data Validation in GGHouse Application

**Requirement:** Make nationality a **required field** for tenant registration

**Implementation:**
```javascript
// Example validation (adjust for actual application)
if (tenant.nationality === null || tenant.nationality === '') {
  throw new ValidationError('Nationality is required');
}

// Prevent レソト unless explicitly confirmed
if (tenant.nationality_id === 200) {
  if (!user.confirmed_lesotho_nationality) {
    throw new ValidationError('レソト nationality requires confirmation');
  }
}
```

#### 4.4 Add ETL Data Quality Check

**Add to `glue/scripts/staging_loader.py`:**
```python
def validate_nationality_data(df):
    """Flag suspicious nationality patterns."""
    lesotho_count = df[df['nationality'] == 'レソト'].shape[0]
    
    if lesotho_count > 10:
        logger.warning(
            f"Suspicious: {lesotho_count} tenants with レソト nationality detected. "
            f"This may indicate data quality issues from source system."
        )
    
    return df
```

### Priority 3: MEDIUM-TERM - dbt Handling (This Month)

#### 4.5 Add レソト Flag to Silver Layer

**Update `dbt/models/silver/stg_tenants.sql`:**
```sql
-- Add data quality flag for レソト placeholder
CASE 
    WHEN t.nationality = 'レソト' AND t.m_nationality_id = 200 THEN 'PLACEHOLDER_FLAG'
    WHEN t.nationality IS NULL OR t.nationality = '' THEN 'MISSING'
    ELSE 'VALID'
END as nationality_data_quality,

-- Replace レソト with explicit "Unknown" label
CASE 
    WHEN t.nationality = 'レソト' AND t.m_nationality_id = 200 THEN 'その他 (Unknown)'
    WHEN {{ clean_string_null('t.nationality') }} IS NOT NULL 
        THEN {{ clean_string_null('t.nationality') }}
    WHEN n.nationality_name IS NOT NULL 
        THEN n.nationality_name
    ELSE 'その他 (Unknown)'
END as nationality,
```

**Benefits:**
- Clear distinction between "unknown" and placeholder data
- Easier filtering in analytics
- Better data traceability

#### 4.6 Add Test for レソト Flag

**Create `dbt/tests/assert_no_lesotho_placeholders.sql`:**
```sql
-- Fail if gold layer contains レソト placeholder records
SELECT 
    'new_contracts' as table_name,
    COUNT(*) as lesotho_count
FROM {{ ref('new_contracts') }}
WHERE nationality = 'レソト'
HAVING COUNT(*) > 0

UNION ALL

SELECT 
    'moveouts' as table_name,
    COUNT(*) as lesotho_count
FROM {{ ref('moveouts') }}
WHERE nationality = 'レソト'
HAVING COUNT(*) > 0;
```

### Priority 4: LONG-TERM - Documentation (Next Month)

#### 4.7 Update Data Dictionary

Add to `docs/DATA_DICTIONARY.md`:

```markdown
### Known Data Quality Issues

#### Nationality Field

**Issue:** レソト (Lesotho) Placeholder Flag
- **Affected Records:** 683 tenants (1.42%)
- **Root Cause:** September 2025 bulk import with missing nationality data
- **Status:** Cleanup in progress (563 active residents prioritized)
- **Handling:** Gold layer filters these records out automatically
- **Contact:** Data Operations team for record corrections
```

---

## 5. SQL Queries for Stakeholders

### 5.1 Export レソト Tenant List for Review

```sql
-- Full list with all available information
SELECT 
    t.id as tenant_id,
    t.full_name,
    t.nationality as current_nationality_flag,
    t.m_nationality_id,
    t.contact_nationality_1 as alternate_nationality,
    t.status as status_code,
    ts.label_en as status_label,
    t.gender_type,
    t.age,
    t.birth_date,
    t.affiliation,
    t.affiliation_type,
    t.contract_type,
    t.created_at,
    t.updated_at,
    m.contract_date,
    m.contract_start_date,
    a.apartment_name,
    r.room_number
FROM staging.tenants t
LEFT JOIN seeds.code_tenant_status ts ON t.status = ts.code
LEFT JOIN staging.movings m ON t.id = m.tenant_id
LEFT JOIN staging.apartments a ON m.apartment_id = a.id
LEFT JOIN staging.rooms r ON m.room_id = r.id
WHERE t.nationality = 'レソト'
ORDER BY t.status, t.created_at DESC;
```

**File exported:** `docs/lesotho_flag_tenants_full_list.tsv` (684 rows)

### 5.2 Monitor Cleanup Progress

```sql
-- Daily tracking query
SELECT 
    DATE(updated_at) as update_date,
    COUNT(*) as lesotho_records_remaining
FROM staging.tenants
WHERE nationality = 'レソト'
GROUP BY DATE(updated_at)
ORDER BY update_date DESC;
```

### 5.3 Verify Gold Layer Protection

```sql
-- Ensure gold tables never contain レソト placeholder
SELECT 
    'new_contracts' as table_name,
    COUNT(*) as lesotho_count,
    CASE WHEN COUNT(*) = 0 THEN '✅ PASS' ELSE '❌ FAIL' END as status
FROM gold.new_contracts
WHERE nationality = 'レソト'

UNION ALL

SELECT 
    'moveouts' as table_name,
    COUNT(*) as lesotho_count,
    CASE WHEN COUNT(*) = 0 THEN '✅ PASS' ELSE '❌ FAIL' END as status
FROM gold.moveouts
WHERE nationality = 'レソト'

UNION ALL

SELECT 
    'moveout_notices' as table_name,
    COUNT(*) as lesotho_count,
    CASE WHEN COUNT(*) = 0 THEN '✅ PASS' ELSE '❌ FAIL' END as status
FROM gold.moveout_notices
WHERE nationality = 'レソト';
```

---

## 6. Exported Files

1. **`docs/lesotho_flag_tenants_full_list.tsv`** (684 rows)
   - Complete list of all tenants with レソト placeholder
   - Includes tenant_id, name, status, demographics, contract info
   - Ready for distribution to data entry team

---

## 7. Action Items & Ownership

| Priority | Action | Owner | Timeline | Status |
|----------|--------|-------|----------|--------|
| 🔴 P1 | Review & correct 563 active resident nationalities | Data Entry Team | 1 week | 🟡 TODO |
| 🔴 P1 | Create manual review queue in GGHouse | Operations Manager | 2 days | 🟡 TODO |
| 🟡 P2 | Add nationality validation to GGHouse app | Dev Team | 2 weeks | 🟡 TODO |
| 🟡 P2 | Implement ETL warning for レソト flag | Data Engineering | 2 weeks | 🟡 TODO |
| 🟢 P3 | Add nationality_data_quality flag in dbt | Data Engineering | 1 month | 🟡 TODO |
| 🟢 P3 | Create dbt test for gold layer レソト | Data Engineering | 1 month | 🟡 TODO |
| 🟢 P4 | Update DATA_DICTIONARY.md | Data Team | 1 month | 🟡 TODO |
| ✅ Done | Investigate & document レソト issue | Data Engineering | - | ✅ COMPLETE |
| ✅ Done | Export レソト tenant list | Data Engineering | - | ✅ COMPLETE |

---

## 8. Stakeholder Communication

### 8.1 Email Template for GGHouse Team

**Subject:** 🚨 Data Quality Issue: 683 Tenant Records with Placeholder Nationality

**Body:**
```
Hi GGHouse Team,

We've identified a data quality issue affecting 683 tenant records in the database.

**Issue Summary:**
- 683 tenant records have nationality set to "レソト" (Lesotho)
- This is a placeholder flag from a September 2025 data import
- These tenants are NOT actually from Lesotho (names are Japanese, Chinese, Russian, etc.)
- 563 of these tenants are currently "In Residence" and need correction

**What We Need:**
1. Please review the attached TSV file (lesotho_flag_tenants_full_list.tsv)
2. Update each tenant's nationality using source contracts/documents
3. Prioritize active residents (status = "In Residence")

**Why This Matters:**
- Accurate nationality data is needed for compliance reporting
- Current data undermines trust in our reporting systems
- Gold layer analytics are unaffected (automatic filtering), but staging/silver data is incorrect

**Timeline:**
- We recommend completing this within 1 week
- ~15 minutes per record, ~140 hours total effort
- Suggest 2 staff members, 4 hours/day for 1 week

Please let me know if you have questions or need assistance.

Best regards,
Data Engineering Team
```

### 8.2 Slack Notification

```
:warning: **Data Quality Alert**: レソト (Lesotho) Nationality Placeholder

We've discovered that 683 tenant records (1.42%) have nationality set to "レソト" as a placeholder from a Sept 2025 data import.

:white_check_mark: Good news: Gold layer analytics unaffected
:x: Issue: 563 active residents have incorrect nationality data

:clipboard: **Action needed**: Data entry team to review attached file
:calendar: **Deadline**: 1 week
:link: Full report: docs/LESOTHO_FLAG_INVESTIGATION.md
```

---

## 9. Appendix: Technical Details

### 9.1 Nationality Lookup Table Entry

```sql
SELECT * FROM staging.m_nationalities WHERE id = 200;
```

| Field | Value |
|-------|-------|
| id | 200 |
| nationality_name | レソト |
| nationality_name_en | NULL |
| nationality_group_id | 0 (Miscellaneous/Other) |
| sort_number | 0 |
| ruby | レソト |

### 9.2 Lesotho Geographic Context

**Lesotho** is a small, landlocked country in Southern Africa:
- Population: ~2.1 million
- Surrounded entirely by South Africa
- Very low international migration to Japan
- **Expected Tokyo Beta residents from Lesotho: ~0**

**Comparison:**
- レソト in database: 683 tenants
- Real Lesotho population in Japan (estimated): < 10
- **Probability these are real Lesotho residents: ~0%**

---

## Conclusion

The レソト (Lesotho) nationality flag represents a **confirmed data quality issue** affecting 683 tenant records (1.42% of total). This was caused by a September 2025 bulk data import where nationality defaulted to ID=200 as a placeholder.

**Impact Assessment:**
- ✅ **Analytics (Gold Layer):** No impact - records properly filtered
- ⚠️ **Operations (Silver Layer):** Medium impact - 563 active residents need correction
- 🔴 **Data Quality:** High impact - undermines trust in nationality reporting

**Next Steps:**
1. Data entry team to review and correct 563 active resident records (Priority 1)
2. Add validation to prevent future レソト placeholder usage (Priority 2)
3. Implement dbt data quality flag and tests (Priority 3)
4. Document in DATA_DICTIONARY.md (Priority 4)

**Status:** Investigation complete ✅ | Cleanup in progress 🟡

---

**Report Completed:** 2026-02-07  
**Next Review:** Weekly until cleanup complete  
**Contact:** Data Engineering Team
