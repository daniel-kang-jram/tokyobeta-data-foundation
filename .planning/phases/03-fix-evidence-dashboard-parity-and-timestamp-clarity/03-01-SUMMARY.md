---
phase: 03-fix-evidence-dashboard-parity-and-timestamp-clarity
plan: 01
subsystem: ui
tags: [evidence, funnel, pricing, parity, timestamps, sql-contracts]
requires:
  - phase: 02-evidence-dashboard-authenticated-uat-and-release-readiness
    provides: authenticated route marker and release smoke contracts
provides:
  - Data-max anchored funnel/pricing window contracts resilient to stale wall-clock time.
  - Moveout->move-in snapshot parity section on the funnel route using gold-backed queries.
  - Explicit query-backed Time basis/Coverage/Freshness labels across funnel and pricing sections.
affects: [route-marker-contracts, evidence-funnel, evidence-pricing, release-smoke]
tech-stack:
  added: []
  patterns:
    - Data-max anchored lookback windows via CTEs and interval offsets.
    - Query-backed timestamp context markers (`Coverage:` and `Freshness:` expressions).
key-files:
  created:
    - scripts/tests/test_evidence_funnel_parity_contract.py
  modified:
    - evidence/pages/funnel.md
    - evidence/pages/pricing.md
    - evidence/sources/aurora_gold/funnel_application_to_movein_daily.sql
    - evidence/sources/aurora_gold/funnel_application_to_movein_periodized.sql
    - evidence/sources/aurora_gold/funnel_application_to_movein_segment_share.sql
key-decisions:
  - "Anchor lookback windows to dataset max dates instead of current_date for stale-data robustness."
  - "Implement moveout->move-in parity directly on funnel page from aurora_gold moveout/movein sources."
  - "Require Coverage/Freshness markers to be query-backed expressions in contract tests."
patterns-established:
  - "Funnel/pricing trend SQL uses local data_max CTE anchors with interval windows."
  - "Timestamp context copy includes Time basis + Coverage + Freshness on each analytical block."
requirements-completed: [EVD-REFRESH-002, EVD-REFRESH-006, EVD-REFRESH-008]
duration: 11 min
completed: 2026-03-02
---

# Phase 03 Plan 01: Funnel Parity and Timestamp Clarity Summary

**Funnel/pricing SQL windows now anchor to data-max dates, with gold-backed moveout->move-in parity and explicit query-driven coverage/freshness labels.**

## Performance

- **Duration:** 11 min
- **Started:** 2026-03-02T02:15:25Z
- **Completed:** 2026-03-02T02:26:37Z
- **Tasks:** 3
- **Files modified:** 6

## Accomplishments
- Added failing-then-passing funnel parity contract tests for anchoring, parity content, and timestamp markers.
- Reworked funnel/pricing queries to avoid wall-clock windows and use data-max anchored lookbacks.
- Added a moveout->move-in snapshot parity section on the funnel route using aurora_gold moveout/movein query contracts.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add failing funnel/parity contract tests (RED)** - `418fc92` (test)
2. **Task 2: Implement data-max anchored queries and parity block (GREEN)** - `17e79e7` (feat)
3. **Task 3: Close RED tests and lock parity contracts (REFACTOR)** - `c3aff34` (refactor)

## Files Created/Modified
- `scripts/tests/test_evidence_funnel_parity_contract.py` - Contract tests for source anchoring, parity sections, and marker stability.
- `evidence/pages/funnel.md` - Added data-max anchored trend queries, parity markers, and moveout->move-in snapshot block.
- `evidence/pages/pricing.md` - Replaced wall-clock filters with data-max anchoring and added explicit Coverage/Freshness labels.
- `evidence/sources/aurora_gold/funnel_application_to_movein_daily.sql` - Added data_max/window anchoring contract.
- `evidence/sources/aurora_gold/funnel_application_to_movein_periodized.sql` - Added grain-aware data_max/window anchoring contract.
- `evidence/sources/aurora_gold/funnel_application_to_movein_segment_share.sql` - Added weekly/monthly data_max/window anchoring contract.

## Decisions Made
- Kept pricing smoke marker strings deterministic and mirrored required marker text on funnel content to avoid route-contract drift.
- Used query-backed interpolation for timestamp copy so `Coverage:` and `Freshness:` are always sourced from dataset output.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] GSD tool path mismatch in local environment**
- **Found during:** Executor initialization (pre-task)
- **Issue:** Workflow default path (`~/.claude/get-shit-done/bin/gsd-tools.cjs`) was missing.
- **Fix:** Switched execution commands to installed path at `~/.codex/get-shit-done/bin/gsd-tools.cjs`.
- **Files modified:** None (execution environment only)
- **Verification:** `node "$HOME/.codex/get-shit-done/bin/gsd-tools.cjs" init execute-phase ...` succeeded.
- **Committed in:** N/A

**2. [Rule 1 - Bug] Initial GREEN queries referenced unavailable columns/functions**
- **Found during:** Task 2 build verification
- **Issue:** Evidence query binder errors for `window_start*` columns and unsupported `date_format(...)`.
- **Fix:** Moved anchored windows into page-level `data_max` CTE contracts and replaced month bucketing with `date_trunc(...)`.
- **Files modified:** `evidence/pages/funnel.md`, `evidence/pages/pricing.md`
- **Verification:** `cd evidence && npm run build` completed without query errors.
- **Committed in:** `17e79e7`

---

**Total deviations:** 2 auto-fixed (1 Rule 3, 1 Rule 1)  
**Impact on plan:** Deviations were required to complete execution in this environment and keep query contracts build-valid; no scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
Ready for `03-02-PLAN.md`. Funnel/pricing parity and timestamp contracts are now deterministic and build-verified.

## Self-Check: PASSED
- Verified required files exist on disk.
- Verified task commit hashes (`418fc92`, `17e79e7`, `c3aff34`) exist in git history.
