---
phase: 04-improve-evidence-ux-readability-and-chart-ergonomics
plan: 02
subsystem: ui
tags: [evidence, geography, pricing, ergonomics, contracts]
requires:
  - phase: 04-improve-evidence-ux-readability-and-chart-ergonomics
    provides: funnel compact-date marker conventions and route contract stability
provides:
  - Geography and pricing chart-height guardrails capped to compact laptop-readable footprints.
  - Dedicated chart ergonomics contract tests for geography hotspots and pricing segment pressure ranking.
  - Concise Time basis/Coverage/Freshness wording with query-backed YYYY-MM-DD formatting on geography and pricing routes.
affects: [phase-04-plan-03, release-guardrails, evidence-geography, evidence-pricing]
tech-stack:
  added: []
  patterns:
    - Section-scoped chart ergonomics assertions to prevent broad false-positive guardrails.
    - Date-only context formatting via SQL `substr(cast(...), 1, 10)` in coverage/freshness helper queries.
key-files:
  created:
    - scripts/tests/test_evidence_chart_ergonomics_contract.py
  modified:
    - evidence/pages/geography.md
    - evidence/pages/pricing.md
    - scripts/tests/test_evidence_geography_contract.py
key-decisions:
  - "Set geography hotspot and pricing segment-pressure chartAreaHeight guardrail to <=560 for reduced scrolling and readable labels."
  - "Preserve deterministic Time basis/Coverage/Freshness prefixes while simplifying note prose to operator-facing language."
  - "Render coverage and freshness values as compact YYYY-MM-DD strings in geography/pricing helper queries."
patterns-established:
  - "Ergonomics Contract Pattern: Assert chart heights by route section (hotspots/ranking) rather than whole-file chartAreaHeight scans."
  - "Compact Context Pattern: Keep marker prefixes stable while reducing prose verbosity and timezone-heavy display."
requirements-completed: [EVD-REFRESH-002, EVD-REFRESH-004, EVD-NFR-001, EVD-NFR-002]
duration: 5 min
completed: 2026-03-02
---

# Phase 4 Plan 2: Geography and Pricing Ergonomics Summary

**Geography hotspot charts and pricing segment ranking now use compact vertical footprints with concise, date-only time-context notes while preserving route contracts.**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-02T05:49:06Z
- **Completed:** 2026-03-02T05:54:29Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments
- Added RED-first chart ergonomics contracts that fail on oversized (`900`) geography/pricing chart footprints and enforce time-context marker presence.
- Reduced geography hotspot and pricing segment-pressure chart heights to `520` and simplified note language without breaking deterministic route headings/palette markers.
- Stabilized height assertions to hotspot/ranking sections and revalidated against geography + funnel parity guardrails and Evidence build.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add failing chart ergonomics contract tests for geography and pricing (RED)** - `bcc0aa9` (test)
2. **Task 2: Implement chart-height tightening and concise note wording on geography/pricing (GREEN)** - `2dae7a0` (feat)
3. **Task 3: Close ergonomics contracts and regression-check existing page guardrails (REFACTOR)** - `ba4ab4b` (refactor)

## Files Created/Modified
- `scripts/tests/test_evidence_chart_ergonomics_contract.py` - New ergonomics contract checks for geography hotspot and pricing ranking chart heights plus marker presence.
- `scripts/tests/test_evidence_geography_contract.py` - Added and refined hotspot-only chart-height guardrails.
- `evidence/pages/geography.md` - Tightened hotspot chart heights and converted coverage/freshness helper outputs + note text to compact date-focused wording.
- `evidence/pages/pricing.md` - Tightened segment-pressure chart height and converted coverage/freshness helper outputs + note text to compact date-focused wording.

## Decisions Made
- Chart ergonomics were enforced with a strict upper bound (`<=560`), implemented as `520` to materially reduce scroll length while maintaining readability.
- Route contract stability remained non-negotiable: existing geography heading/palette markers and all Time basis/Coverage/Freshness prefixes were preserved.
- Date compactness was implemented in SQL coverage/freshness helper projections to keep display deterministic and avoid timezone-heavy text.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Phase 4 plan 02 ergonomics and marker contracts are green and build-verified.
- Ready to execute `04-03-PLAN.md` with no blockers identified.

---
*Phase: 04-improve-evidence-ux-readability-and-chart-ergonomics*
*Completed: 2026-03-02*

## Self-Check: PASSED

- Found `.planning/phases/04-improve-evidence-ux-readability-and-chart-ergonomics/04-02-SUMMARY.md`.
- Found `scripts/tests/test_evidence_chart_ergonomics_contract.py`.
- Verified task commits: `bcc0aa9`, `2dae7a0`, `ba4ab4b`.
