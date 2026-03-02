---
phase: 04-improve-evidence-ux-readability-and-chart-ergonomics
plan: 01
subsystem: ui
tags: [evidence, funnel, sankey, contracts, readability]
requires:
  - phase: 03-fix-evidence-dashboard-parity-and-timestamp-clarity
    provides: anchored funnel windows, route guardrail marker contracts
provides:
  - Funnel replacement-failure sankey flow with deterministic red move-out and green move-in links.
  - Funnel contract tests aligned to intentional breakdown removals and flow marker contracts.
  - Compact date-style Time basis/Coverage/Freshness wording for funnel operator context.
affects: [phase-04-plan-02, phase-04-plan-03, release-guardrails]
tech-stack:
  added: []
  patterns:
    - Deterministic flow marker contracts via markdown heading/query/component markers.
    - Query-backed date-only coverage/freshness labels through SQL string projection.
key-files:
  created: []
  modified:
    - evidence/pages/funnel.md
    - scripts/tests/test_evidence_funnel_parity_contract.py
key-decisions:
  - "Remove low-signal municipality/nationality/trend breakdown charts from funnel while retaining pricing route parity markers."
  - "Model replacement flow links from aurora_gold moveout/movein sources grouped by municipality, nationality, tenant_type, and rent_band."
  - "Keep Time basis/Coverage/Freshness prefixes but emit compact YYYY-MM-DD values for funnel notes."
patterns-established:
  - "Flow Contract Pattern: Use explicit marker strings and link_type color branches for deterministic contract tests."
  - "Compact Date Context Pattern: Convert date/time fields to date-only strings in coverage helper queries."
requirements-completed: [EVD-REFRESH-002, EVD-REFRESH-004, EVD-REFRESH-006, EVD-REFRESH-008]
duration: 6 min
completed: 2026-03-02
---

# Phase 4 Plan 1: Funnel Replacement-Flow Ergonomics Summary

**Funnel route now uses a snapshot-style replacement-failure sankey flow with deterministic red/green contracts and compact operator-facing time context.**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-02T05:37:56Z
- **Completed:** 2026-03-02T05:44:37Z
- **Tasks:** 3
- **Files modified:** 2

## Accomplishments
- Replaced funnel’s low-signal conversion breakdown sections with a `Killer Chart: Replacement Failure Flow` section and sankey flow links.
- Preserved municipality/nationality/cohort (`tenant_type`) context by encoding segment keys with rent band in the replacement flow query contract.
- Updated funnel parity contract tests to intentionally enforce new flow markers, preserved pricing markers, and removed funnel-only sections.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add failing funnel flow contract tests (RED)** - `7b83cc6` (test)
2. **Task 2: Implement snapshot-style replacement-failure flow and remove low-signal funnel breakdowns (GREEN)** - `e25a186` (feat)
3. **Task 3: Close funnel contracts and verify Phase 3 guardrails remain intact (REFACTOR)** - `9d9715c` (refactor)

## Files Created/Modified
- `scripts/tests/test_evidence_funnel_parity_contract.py` - Added killer-flow marker contracts, dimension-preservation checks, and funnel-only breakdown-removal assertions.
- `evidence/pages/funnel.md` - Implemented replacement-failure sankey chart, flow summary KPIs, compact date context notes, and removed low-signal breakdown sections.

## Decisions Made
- Funnel section contracts intentionally diverge from pricing: pricing keeps existing parity markers while funnel now centers on replacement failure flow.
- Sankey links use explicit `link_type` branches (`out`/`in`) to keep red/green semantics deterministic for test contracts.
- Coverage and freshness values on funnel are rendered as compact date-only strings to avoid verbose timezone-oriented display.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- Task 3 initially failed one marker assertion because the flow color branch did not explicitly include `d.link_type === 'in'`; fixed with an explicit in-branch and re-verified.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Phase 4 plan 01 contracts are stable and verified; ready to execute `04-02-PLAN.md`.
- No blockers identified for subsequent plan execution.

---
*Phase: 04-improve-evidence-ux-readability-and-chart-ergonomics*
*Completed: 2026-03-02*

## Self-Check: PASSED

- Found `.planning/phases/04-improve-evidence-ux-readability-and-chart-ergonomics/04-01-SUMMARY.md`.
- Verified task commits: `7b83cc6`, `e25a186`, `9d9715c`.
