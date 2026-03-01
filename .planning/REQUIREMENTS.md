# Requirements

## Functional

- [x] `EVD-REFRESH-001` KPI-first landing page in gold dashboard with occupancy and operating totals.
- [x] `EVD-REFRESH-002` Migrate key snapshot sections (geography, funnel, pie/segment) into gold-connected dashboard.
- [x] `EVD-REFRESH-003` KPI cards include RENT, RevPAR, and RecPAR(Cash) when source data quality allows.
- [x] `EVD-REFRESH-004` Every KPI/chart/table shows explicit time basis (`as_of_date` or period) and freshness metadata.
- [x] `EVD-REFRESH-005` Add configurable timespan control (daily/weekly/monthly where available) for major sections.
- [x] `EVD-REFRESH-006` Extend funnel to include application -> move-in conversion by municipality and nationality profile.
- [ ] `EVD-REFRESH-007` Support CSV export for core analytical tables where useful for operator workflows.
- [x] `EVD-REFRESH-008` Add filters for corporate vs individual cohort views where distinction affects funnel interpretation.

## Data & Metric Integrity

- [x] `EVD-DQ-001` Occupancy logic handles edge cases (e.g., same-day move-out interpretation) and is documented.
- [x] `EVD-DQ-002` KPI definitions are versioned and traceable to SQL/model logic.
- [x] `EVD-DQ-003` Benchmark checks include known reference points from Feb 2026 communications:
  - 2026-01-31 month-end occupancy rate target reference: 70.7%
  - 2026-01 month-end references: RENT 56,195 / RevPAR 39,757 / RecPAR(Cash) 37,826
  - 2026-02-01 00:00 occupancy rooms reference: 11,271 (11,295 including 2/1 new)

## Non-Functional

- [x] `EVD-NFR-001` Dashboard must clearly communicate timestamp context to prevent reporting confusion.
- [x] `EVD-NFR-002` Data freshness/source trace remains visible and understandable to non-technical users.
