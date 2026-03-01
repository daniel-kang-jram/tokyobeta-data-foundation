# Deferred Items

## 2026-03-01 - Out-of-scope Build Warnings During 01-03 Execution

- Evidence build warnings/errors from `evidence/pages/pricing.md` due missing `snapshot_csv` tables:
  - `snapshot_csv.rent_band_inout_balance`
  - `snapshot_csv.occupancy_by_room_feature`
  - `snapshot_csv.property_risk_rank`
  - `snapshot_csv.insight_bullets`
- Classification: pre-existing and unrelated to Plan `01-03` scope (index/funnel + gold wrappers).
- Action deferred: migrate/remove snapshot-csv pricing dependencies in a dedicated plan.
