---
phase: 01-evidence-gold-kpi-refresh
plan: 01
subsystem: database
tags: [dbt, occupancy, kpi, evidence]
requires:
  - phase: none
    provides: base gold/silver occupancy datasets
provides:
  - Canonical KPI contract model for occupancy, RENT, RevPAR, and RecPAR(Cash)
  - Explicit same-day move-out policy contract and benchmark assertions
  - KPI freshness/source trace model for Evidence metadata blocks
affects: [evidence-kpi-cards, data-quality-guardrails, benchmark-reconciliation]
tech-stack:
  added: []
  patterns: [versioned metric contract, tolerance-based benchmark assertions, policy-token validation]
key-files:
  created:
    - dbt/models/gold/kpi_month_end_metrics.sql
    - dbt/models/gold/kpi_month_end_metrics.yml
    - dbt/models/gold/kpi_reference_trace.sql
    - dbt/tests/assert_kpi_reference_feb2026.sql
    - dbt/tests/assert_occupancy_same_day_moveout_policy.sql
  modified:
    - docs/DATA_MODEL.md
    - docs/OCCUPANCY_KPI_DEPLOYMENT.md
key-decisions:
  - "Use a single gold KPI contract (`gold.kpi_month_end_metrics`) with explicit `kpi_definition_version`."
  - "Encode same-day occupancy behavior via policy token: `count_moveout_room_at_0000_exclude_same_day_moveins`."
  - "Use tolerance-based benchmark assertions to keep checks deterministic across upstream snapshot drift."
patterns-established:
  - "Room-primary occupancy baseline at 00:00 with same-day move-in exclusion."
  - "Trace model (`gold.kpi_reference_trace`) as the canonical freshness/source metadata surface."
requirements-completed: [EVD-REFRESH-003, EVD-REFRESH-004, EVD-DQ-001, EVD-DQ-002, EVD-DQ-003]
duration: 11 min
completed: 2026-03-01
---

# Phase 1 Plan 1: KPI Contract Refresh Summary

**Canonical gold KPI contract for occupancy and room-economics with benchmarked Feb 2026 references and traceable policy/version metadata**

## Performance

- **Duration:** 11 min
- **Started:** 2026-03-01T14:23:54Z
- **Completed:** 2026-03-01T14:35:07Z
- **Tasks:** 3
- **Files modified:** 7

## Accomplishments
- Added new canonical KPI mart `gold.kpi_month_end_metrics` with shared as-of context and version field.
- Added benchmark and policy singular tests that now pass against implemented KPI contract.
- Added `gold.kpi_reference_trace` and aligned documentation for KPI ownership and policy semantics.

## Task Commits

Each task was committed atomically:

1. **Task 1: Write failing benchmark and occupancy-policy tests (RED)** - `94e5057` (test)
2. **Task 2: Implement canonical month-end KPI model with versioned definitions (GREEN)** - `f29dfb9` (feat)
3. **Task 3: Add freshness trace model and close RED tests (REFACTOR)** - `5cae750` (refactor)

## Files Created/Modified
- `dbt/models/gold/kpi_month_end_metrics.sql` - Canonical KPI contract table and policy/version fields.
- `dbt/models/gold/kpi_month_end_metrics.yml` - Model tests and KPI column documentation.
- `dbt/models/gold/kpi_reference_trace.sql` - As-of freshness/source metadata trace surface.
- `dbt/tests/assert_kpi_reference_feb2026.sql` - Jan/Feb 2026 benchmark tolerance assertions.
- `dbt/tests/assert_occupancy_same_day_moveout_policy.sql` - Same-day occupancy policy regression guard.
- `docs/DATA_MODEL.md` - Added KPI contract ownership mapping.
- `docs/OCCUPANCY_KPI_DEPLOYMENT.md` - Added canonical policy and benchmark interpretation notes.

## Decisions Made
- Standardized dashboard KPI cards on `gold.kpi_month_end_metrics` rather than mixed model/page SQL definitions.
- Kept benchmark checks tolerance-based to preserve deterministic CI behavior while still catching regressions.
- Exposed same-day occupancy semantics as an explicit policy token and enforced it in tests.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Updated executor tool path from `~/.claude` to `~/.codex`**
- **Found during:** Initialization
- **Issue:** Plan workflow referenced a non-existent local tool path, blocking state updates.
- **Fix:** Switched all gsd-tools invocations to `~/.codex/get-shit-done/bin/gsd-tools.cjs`.
- **Files modified:** None (execution-path fix)
- **Verification:** `node ... init execute-phase 01` succeeded.
- **Committed in:** N/A (runtime execution fix)

**2. [Rule 1 - Bug] Zero-denominator KPI rows produced null rent/revpar/recpar**
- **Found during:** Final verification
- **Issue:** Early dates with zero 00:00 occupied rooms produced null KPI values and failed model tests.
- **Fix:** Defaulted rent/revpar/recpar path to `0` when denominator is zero.
- **Files modified:** `dbt/models/gold/kpi_month_end_metrics.sql`
- **Verification:** `dbt test --select kpi_month_end_metrics kpi_reference_trace assert_kpi_reference_feb2026 assert_occupancy_same_day_moveout_policy --profiles-dir .` passed.
- **Committed in:** `5cae750`

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 bug)
**Impact on plan:** Both fixes were required to complete execution and keep KPI contract tests reliable; no scope creep introduced.

## Issues Encountered
- Initial RED run selected no nodes because the target model did not exist yet; expected during test-first sequence.
- Final consolidated verification surfaced null KPI edge-case rows; fixed inline and re-verified.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- KPI source contract, benchmark checks, and trace metadata are in place for Evidence consumption.
- Ready for the next phase plan (`01-02-PLAN.md`).

## Self-Check: PASSED

- Verified required artifacts exist on disk.
- Verified task commits `94e5057`, `f29dfb9`, and `5cae750` exist in git history.

---
*Phase: 01-evidence-gold-kpi-refresh*
*Completed: 2026-03-01*
