# Rent Roll vs Gold Table Analysis - Summary

**Date**: February 9, 2026
**Status**: ✅ Rent Roll Analyzed | ⏳ Awaiting Gold Table Comparison

---

## Quick Summary

I've successfully parsed and analyzed your rent roll Excel file (`data/RRデータ出力20251203.xlsx`). Here's what I found:

### Rent Roll Data (October 2025)
- **1,076 active tenants** in the most recent complete period (October 2025)
- **16,547 unique property units** tracked historically
- **1,048,575 total records** (monthly snapshots from 2022-2025)

### Top Corporate Tenants
1. ㈱K&Kコンサルティング - 6,696 historical records
2. メブキ㈱ - 5,383 records
3. ㈱ベアーズ - 4,076 records
4. ㈱リロエステート - 3,643 records
5. 法人一棟 - 3,258 records

---

## What's Next

To complete the reconciliation, you need to **query your Aurora gold table** to compare active tenant counts. The database is in a private subnet, so you'll need to:

### Option 1: Use the Quick Check Script
```bash
cd /Users/danielkang/tokyobeta-data-consolidation
./scripts/quick_db_check.sh
```

This will:
- Retrieve Aurora credentials from AWS Secrets Manager
- Query active tenant counts
- Show breakdown by contract type
- Compare with rent roll data

### Option 2: Use dbt (If Tunneled to Database)
```bash
cd dbt
dbt run --select active_tenant_count_check
```

### Option 3: Connect via Bastion/EC2 Instance
SSH into an EC2 instance that has access to Aurora, then:
```bash
# On EC2 instance
mysql -h tokyobeta-prod-aurora-cluster.cluster-cr46qo6y4bbb.ap-northeast-1.rds.amazonaws.com \
      -u admin -p tokyobeta

# Then run:
SELECT COUNT(DISTINCT t.id) as active_tenant_count
FROM staging.tenants t
INNER JOIN silver.code_tenant_status s ON t.status = s.code
WHERE s.is_active_lease = 1;
```

---

## Key Questions to Answer

Once you query the gold table:

1. **What's the current active tenant count?**
   - Expected: ~1,000-1,300 (given 1,076 in Oct 2025)
   - If significantly different, investigate why

2. **How does it break down by contract type?**
   - Corporate vs Individual
   - Any "unknown" types?

3. **Are there discrepancies?**
   - Time lag (Oct 2025 → Feb 2026): ±50-200 normal
   - Definition mismatch: Check if status codes align
   - Data quality: Investigate if >5% variance

---

## Files Created

### Analysis Scripts
- `scripts/count_unique_active_tenants.py` - Analyzes rent roll for active tenants
- `scripts/quick_db_check.sh` - Queries Aurora gold table (when accessible)
- `scripts/query_gold_active_tenants.py` - Python version of database query

### Reports
- `docs/RENT_ROLL_RECONCILIATION_20260209.md` - Detailed reconciliation report (5,000+ words)
- `dbt/models/analysis/active_tenant_count_check.sql` - dbt model for gold table query

### Sample Outputs
```
Rent Roll Active Tenants by Period:
  2025-10: 1,076 active tenants
  2025-09: 1,236 active tenants
  2025-08: 374 active tenants
  2025-07: 143 active tenants
  (older periods omitted)
```

---

## Expected Comparison Results

| Metric | Rent Roll (Oct 2025) | Gold Table (Feb 2026) | Variance |
|--------|---------------------|---------------------|----------|
| **Active Tenants** | 1,076 | [TO BE QUERIED] | ± 5-10% expected |
| **Corporate** | ~400-500* | [TO BE QUERIED] | Check bulk contracts |
| **Individual** | ~600-700* | [TO BE QUERIED] | Should align closely |

*Estimated based on top corporate tenants in rent roll

---

## Potential Issues to Watch For

### ⚠️ Stale Data in Rent Roll
- **Finding**: 1,840 units (63%) show last activity before October 2025
- **Impact**: May undercount actual active tenants
- **Action**: Investigate these units in gold table

### ⚠️ Corporate Bulk Contracts
- **Finding**: "法人一棟" entries may represent entire buildings
- **Impact**: Gold table may count individual tenants differently
- **Action**: Reconcile aggregation methods

### ⚠️ Definition Mismatch
- **Rent Roll**: Uses `ocp=1` (occupancy flag)
- **Gold Table**: Uses status codes (4,5,6,7,9,14,15)
- **Impact**: May cause systematic variance
- **Action**: Sample 20-30 tenants to verify alignment

---

## How to Interpret Results

### ✅ Good (< 5% variance)
```
Rent Roll: 1,076 active tenants (Oct 2025)
Gold Table: 1,050-1,100 (Feb 2026)
→ Within expected range, accounting for time lag
```

### ⚠️ Investigate (5-15% variance)
```
Rent Roll: 1,076 active tenants (Oct 2025)
Gold Table: 920-1,020 or 1,150-1,250 (Feb 2026)
→ Check for definition mismatch or data quality issues
```

### 🚨 Critical (> 15% variance)
```
Rent Roll: 1,076 active tenants (Oct 2025)
Gold Table: < 920 or > 1,250 (Feb 2026)
→ Systematic issue - investigate immediately:
  • Different active tenant definitions
  • Missing data in one system
  • Corporate tenant counting method
  • Data synchronization problem
```

---

## Commands Reference

### Analyze Rent Roll Again (If Needed)
```bash
python3 scripts/count_unique_active_tenants.py
```

### Query Gold Table
```bash
# If you have direct access
./scripts/quick_db_check.sh

# Or via dbt
cd dbt && dbt run --select active_tenant_count_check
```

### Re-parse Rent Roll Structure
```bash
python3 scripts/quick_rent_roll_parse.py
```

---

## Additional Analysis Available

If you want deeper analysis, I can:

1. **Identify specific units** with stale data in rent roll
2. **Compare tenant names** between rent roll and gold table
3. **Analyze move-in/move-out trends** from rent roll history
4. **Track occupancy rate changes** over time (2022-2025)
5. **Reconcile specific properties** (by asset_id)

Just let me know what you need!

---

## Contact & Support

**Analysis Scripts Location**: `/scripts/`
**Documentation**: `/docs/RENT_ROLL_RECONCILIATION_20260209.md`
**dbt Models**: `/dbt/models/analysis/`

For questions:
- Check detailed reconciliation report: `docs/RENT_ROLL_RECONCILIATION_20260209.md`
- Review analysis scripts for methodology
- Run `quick_db_check.sh` when database access is available

---

**Status**: ✅ Rent Roll analysis complete | Next: Query gold table for comparison
