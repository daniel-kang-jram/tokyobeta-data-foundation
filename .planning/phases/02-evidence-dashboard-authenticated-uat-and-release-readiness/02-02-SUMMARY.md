---
phase: 02-evidence-dashboard-authenticated-uat-and-release-readiness
plan: 02
subsystem: testing
tags: [playwright, evidence, smoke-test, github-actions, route-contract, uat]

requires:
  - phase: 02-evidence-dashboard-authenticated-uat-and-release-readiness
    provides: Canonical metadata route path normalization and build route-contract verification from plan 02-01
provides:
  - Authenticated Playwright smoke script with deterministic route matrix and pricing funnel checks
  - Contract tests enforcing smoke script/workflow route, metadata, and artifact requirements
  - Scheduled/manual GitHub workflow that runs production smoke checks and uploads artifacts
affects: [authenticated-uat, release-readiness, evidence-smoke-gates]

tech-stack:
  added: [playwright]
  patterns:
    - Route assertions are encoded in a deterministic machine-checkable matrix via --print-route-matrix.
    - Smoke output is persisted as reproducible release artifacts (screenshots, console logs, network logs, summary JSON).

key-files:
  created:
    - .planning/phases/02-evidence-dashboard-authenticated-uat-and-release-readiness/02-02-SUMMARY.md
    - scripts/evidence/evidence_auth_smoke.mjs
    - scripts/tests/test_evidence_authenticated_smoke_contract.py
    - .github/workflows/evidence-auth-smoke.yml
  modified: []

key-decisions:
  - "Expose the route assertion contract through --print-route-matrix so jq-based checks can deterministically gate release validation."
  - "Support a dry-run mode that does not require credentials, enabling contract verification in local/CI preflight contexts."
  - "Run production smoke from a dedicated workflow with always-on artifact upload for sign-off evidence."

patterns-established:
  - "Authenticated route UAT now uses one shared route matrix for H1/KPI/time-context/funnel assertions across script and CI verification."

requirements-completed:
  - EVD-REL-001
  - EVD-REL-002
  - EVD-REL-003
  - EVD-REL-004

duration: 6min
completed: 2026-03-01
---

# Phase 02 Plan 02: Authenticated Smoke Matrix + Release Workflow Summary

**Authenticated production smoke now enforces deterministic route marker contracts (including pricing funnel checks) and publishes reproducible artifacts through a dedicated GitHub workflow**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-01T17:18:03Z
- **Completed:** 2026-03-01T17:23:16Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments
- Added RED contract tests that define required routes, route matrix schema, funnel markers, metadata guards, and artifact/workflow expectations.
- Implemented `scripts/evidence/evidence_auth_smoke.mjs` with authenticated Playwright assertions, metadata JSON verification, malformed `/api//` detection, and deterministic route matrix export.
- Added `.github/workflows/evidence-auth-smoke.yml` with manual + scheduled execution, Playwright runtime setup, and `upload-artifact` on `always()`.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add failing smoke contract tests before implementation (RED)** - `fc4f4da` (test)
2. **Task 2: Implement authenticated Playwright smoke script with deterministic route matrix assertions (GREEN)** - `062d674` (feat)
3. **Task 3: Add GitHub workflow for production authenticated smoke and close RED tests (REFACTOR)** - `3013c63` (refactor)

## Files Created/Modified
- `scripts/tests/test_evidence_authenticated_smoke_contract.py` - Contract tests for route matrix schema, funnel assertions, metadata safeguards, and workflow artifact contract.
- `scripts/evidence/evidence_auth_smoke.mjs` - Authenticated Playwright smoke runner with deterministic route matrix output and artifact generation.
- `.github/workflows/evidence-auth-smoke.yml` - Scheduled/manual production smoke workflow with artifact upload.
- `.planning/phases/02-evidence-dashboard-authenticated-uat-and-release-readiness/02-02-SUMMARY.md` - Execution summary for plan 02-02.

## Decisions Made
- Centralized route assertions in one in-script matrix to keep route gates deterministic and machine-checkable.
- Added dry-run and print modes separately so matrix contract validation can run without requiring live credentials.
- Configured workflow artifact upload with `if: always()` so failures still produce debugging evidence for release triage.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `gsd-tools` state/requirements commands could not fully parse current planning file format**
- **Found during:** Post-task state updates
- **Issue:** `state advance-plan`, `state update-progress`, `state record-session`, and `requirements mark-complete` reported parse/not-found errors against the current `.planning` markdown structure.
- **Fix:** Applied the missing updates directly in `.planning/STATE.md`, `.planning/ROADMAP.md`, and `.planning/REQUIREMENTS.md` so plan progress, next-plan pointer, metrics row format, session marker, and requirement checkboxes are consistent.
- **Files modified:** `.planning/STATE.md`, `.planning/ROADMAP.md`, `.planning/REQUIREMENTS.md`
- **Verification:** Re-read files to confirm plan progress is `2/4`, roadmap marks `02-02` complete, and `EVD-REL-003`/`EVD-REL-004` are checked.
- **Committed in:** docs metadata commit

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Deviation was limited to execution bookkeeping; implementation scope and deliverables were unchanged.

## Issues Encountered
- A transient `.git/index.lock` blocked one commit attempt; resolved by retrying commit after lock cleared.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Route marker/funnel/metadata smoke checks are now codified and reproducible for release gating.
- Phase 02-03 can wire these checks into broader CI/deploy guardrails without redefining route contracts.

## Self-Check: PASSED
- FOUND: `.planning/phases/02-evidence-dashboard-authenticated-uat-and-release-readiness/02-02-SUMMARY.md`
- FOUND: `fc4f4da`
- FOUND: `062d674`
- FOUND: `3013c63`

---
*Phase: 02-evidence-dashboard-authenticated-uat-and-release-readiness*
*Completed: 2026-03-01*
