---
phase: 03-fix-evidence-dashboard-parity-and-timestamp-clarity
plan: 04
subsystem: ui
tags: [evidence, smoke-tests, release-guardrails, runbooks, coverage-markers]
requires:
  - phase: 03-01
    provides: Query-backed timestamp marker contracts on prior routes.
  - phase: 03-02
    provides: Authenticated route matrix smoke framework and CI guardrails.
  - phase: 03-03
    provides: Home/occupancy timestamp clarity baseline and route contract hardening.
provides:
  - Coverage marker contract enforcement on occupancy, moveins, and moveouts routes.
  - Deterministic smoke route-matrix `coverage_markers` schema checks.
  - Operations/deployment runbook release gates for coverage marker verification.
affects: [evidence-release, smoke-contracts, deployment-go-no-go, dashboard-parity]
tech-stack:
  added: []
  patterns:
    - Route-matrix marker groups must include explicit `coverage_markers`.
    - Release decisions are blocked when Coverage markers are missing on gated routes.
key-files:
  created: []
  modified:
    - evidence/pages/occupancy.md
    - evidence/pages/moveins.md
    - evidence/pages/moveouts.md
    - scripts/evidence/evidence_auth_smoke.mjs
    - scripts/tests/test_evidence_authenticated_smoke_contract.py
    - scripts/tests/test_evidence_release_guardrails.py
    - docs/OPERATIONS.md
    - docs/DEPLOYMENT.md
key-decisions:
  - "Require `coverage_markers` as a first-class smoke route-matrix field and assert it per gated route."
  - "Back Coverage labels with explicit SQL coverage queries on each remaining parity page section."
  - "Tie GO/NO-GO runbook checks to jq-verified route-matrix coverage markers."
patterns-established:
  - "Marker contract pattern: Time basis + Coverage + Freshness on all release-gated Evidence pages."
  - "Runbook contract pattern: include deterministic jq checks for route-matrix marker groups."
requirements-completed: [EVD-REFRESH-004, EVD-NFR-001, EVD-NFR-002, EVD-REL-004, EVD-REL-005]
duration: 5 min
completed: 2026-03-02
---

# Phase 3 Plan 4: Timestamp Coverage Release Guardrails Summary

**Coverage-marker parity is now enforced across occupancy/moveins/moveouts pages, smoke contracts, and release runbooks.**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-02T03:30:06Z
- **Completed:** 2026-03-02T03:35:56Z
- **Tasks:** 3
- **Files modified:** 8

## Accomplishments
- Added RED guardrail tests that fail when release routes lack deterministic `coverage_markers` or page `Coverage:` labels.
- Implemented query-backed `Coverage:` labels on occupancy, moveins, and moveouts pages and enforced them in authenticated smoke assertions.
- Updated operations and deployment runbooks so release verification explicitly checks coverage markers and treats failures as NO-GO blockers.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add failing coverage-marker guardrail tests (RED)** - `d9efdc1` (test)
2. **Task 2: Implement remaining page coverage labels and smoke matrix enforcement (GREEN)** - `db3a3df` (feat)
3. **Task 3: Update runbooks with coverage-based release criteria and close verification loop (REFACTOR)** - `6d61000` (refactor)

## Files Created/Modified
- `scripts/tests/test_evidence_authenticated_smoke_contract.py` - Adds failing-first coverage-marker route matrix/page marker assertions.
- `scripts/tests/test_evidence_release_guardrails.py` - Enforces coverage-marker smoke contract and docs alignment checks.
- `scripts/evidence/evidence_auth_smoke.mjs` - Adds `coverage_markers` to route schema/results and runtime marker assertions.
- `evidence/pages/occupancy.md` - Adds query-backed coverage bounds and explicit Coverage note.
- `evidence/pages/moveins.md` - Adds period/segment/detail coverage queries and Coverage notes.
- `evidence/pages/moveouts.md` - Adds period/segment/detail coverage queries and Coverage notes.
- `docs/OPERATIONS.md` - Adds coverage-aware marker grep/jq verification and blocker language.
- `docs/DEPLOYMENT.md` - Adds coverage-marker jq checks and GO/NO-GO coverage gate language.

## Decisions Made
- Use route-matrix JSON (`--print-route-matrix`) as the deterministic source for validating coverage-marker contracts.
- Keep coverage labels query-backed per section (period, segment, detail) to avoid static or ambiguous date-window text.
- Require coverage-marker checks in operational and deployment sign-off commands to make release gating auditable.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Phase 03 now has summaries for all plans (`03-01` to `03-04`) and is ready for transition/verification.

## Self-Check: PASSED
- Found summary file on disk.
- Verified task commits: `d9efdc1`, `db3a3df`, `6d61000`.

---
*Phase: 03-fix-evidence-dashboard-parity-and-timestamp-clarity*
*Completed: 2026-03-02*
