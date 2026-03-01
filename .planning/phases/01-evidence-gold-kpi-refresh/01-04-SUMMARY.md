---
phase: 01-evidence-gold-kpi-refresh
plan: 04
subsystem: ui
tags: [evidence, aurora_gold, parity, freshness, csv-export]

requires:
  - phase: 01-03
    provides: KPI and funnel gold source contracts with section-level metadata pattern
provides:
  - Geography and pricing parity pages on gold-backed contracts only
  - Move-in/move-out profile pages with daily/weekly/monthly controls and cohort views
  - Operations runbook acceptance checks for page-source parity and metadata/export verification
affects: [evidence-pages, operations-runbook, incident-response]

tech-stack:
  added: []
  patterns:
    - Section-level Time basis/Freshness notes for every operator-facing visual block
    - CSV-downloadable DataTables for parity-critical operational drilldowns
    - Pricing parity driven by funnel segment-share contract instead of snapshot CSV artifacts

key-files:
  created:
    - .planning/phases/01-evidence-gold-kpi-refresh/01-04-SUMMARY.md
  modified:
    - evidence/pages/geography.md
    - evidence/pages/pricing.md
    - evidence/pages/moveins.md
    - evidence/pages/moveouts.md
    - docs/OPERATIONS.md

key-decisions:
  - "Use `aurora_gold.funnel_application_to_movein_segment_share` as the pricing parity contract and remove all `snapshot_csv` usage."
  - "Implement move profile period controls with daily (`*_analysis_recent`), weekly (`move_events_weekly`), and monthly (`move*_profile_monthly`) sources."
  - "Require explicit `Time basis:` and `Freshness:` labels plus CSV exports on operator drilldown tables."

patterns-established:
  - "Parity pages must document time basis and freshness inline with each major chart/table section."
  - "Evidence parity verification is runbook-driven with page-to-source mapping checks."

requirements-completed:
  - EVD-REFRESH-002
  - EVD-REFRESH-004
  - EVD-REFRESH-005
  - EVD-REFRESH-007
  - EVD-REFRESH-008
  - EVD-NFR-001
  - EVD-NFR-002

duration: 9min
completed: 2026-03-01
---

# Phase 01 Plan 04: Snapshot Parity Surface Refresh Summary

**Gold-backed geography, pricing segment parity, and move profile operational pages with period controls, freshness context, and CSV-ready drilldowns**

## Performance

- **Duration:** 9 min
- **Started:** 2026-03-01T14:51:22Z
- **Completed:** 2026-03-01T15:00:35Z
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments
- Migrated pricing parity analysis from `snapshot_csv` sources to gold funnel segment-share and periodized contracts.
- Added explicit section-level `Time basis:` and `Freshness:` labels across geography, pricing, move-ins, and move-outs parity sections.
- Added an operations runbook section with executable parity, metadata, and CSV-export acceptance checks for `index`, `funnel`, `geography`, `pricing`, `moveins`, and `moveouts`.

## Task Commits

Each task was committed atomically:

1. **Task 1: Migrate geography and pricing parity surfaces to gold-only sources** - `7aee618` (feat)
2. **Task 2: Add period/cohort controls and export-ready tables to move profile pages** - `818bb21` (feat)
3. **Task 3: Update operations runbook with parity-critical acceptance checks** - `ef3fc09` (docs)

## Files Created/Modified
- `.planning/phases/01-evidence-gold-kpi-refresh/01-04-SUMMARY.md` - Execution summary for plan 01-04.
- `evidence/pages/geography.md` - Added per-section metadata labels and export-ready weekly detail tables.
- `evidence/pages/pricing.md` - Rebuilt pricing parity page on funnel segment-share/periodized gold contracts.
- `evidence/pages/moveins.md` - Added daily/weekly/monthly controls, cohort breakdowns, and CSV drilldowns.
- `evidence/pages/moveouts.md` - Added daily/weekly/monthly controls, cohort/reason breakdowns, and CSV drilldowns.
- `docs/OPERATIONS.md` - Added Evidence gold refresh verification runbook with page-to-source acceptance checks.

## Decisions Made
- Pricing parity now treats `funnel_application_to_movein_segment_share` as the canonical segment contract.
- Move profile pages use mixed-grain gold sources explicitly to satisfy period controls where data exists.
- Operational acceptance checks are documented as mandatory commands in `docs/OPERATIONS.md`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed unsupported SQL date formatting in move profile monthly filters**
- **Found during:** Task 2 (Add period/cohort controls and export-ready tables to move profile pages)
- **Issue:** `date_format`/`date_sub` expressions in new page SQL are unsupported in the Evidence runtime SQL dialect.
- **Fix:** Replaced those filters with `cast(month_start as date) >= date_trunc('month', current_date - interval 12 month)`.
- **Files modified:** `evidence/pages/moveins.md`, `evidence/pages/moveouts.md`
- **Verification:** `cd evidence && npm run build` completed, and Task 2 page contract verification script passed.
- **Committed in:** `818bb21` (part of Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Fix was required for build compatibility and did not change planned scope.

## Issues Encountered
- Evidence build reported dataset-empty chart warnings in existing sections due to environment data availability; these warnings are non-blocking and build completed successfully.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Parity-critical Evidence pages and operator verification workflow are aligned to gold contracts.
- Project state can advance from `01-04-PLAN.md` with no open blockers.

## Self-Check: PASSED
- FOUND: `.planning/phases/01-evidence-gold-kpi-refresh/01-04-SUMMARY.md`
- FOUND: `7aee618`
- FOUND: `818bb21`
- FOUND: `ef3fc09`

---
*Phase: 01-evidence-gold-kpi-refresh*
*Completed: 2026-03-01*
