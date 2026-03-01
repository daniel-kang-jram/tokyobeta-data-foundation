---
phase: 02-evidence-dashboard-authenticated-uat-and-release-readiness
plan: 01
subsystem: ui
tags: [evidence, routing, metadata, regression-tests, release-gates]

requires:
  - phase: 01-evidence-gold-kpi-refresh
    provides: KPI-centric pages and authenticated route targets for production Evidence dashboard
provides:
  - Canonical metadata route path composition for root and authenticated route pages
  - Regression tests preventing malformed `/api//.../evidencemeta.json` route metadata fetches
  - Build-artifact route contract verifier for required route metadata references
affects: [authenticated-uat, evidence-release-readiness, ci-route-guardrails]

tech-stack:
  added: []
  patterns:
    - Route metadata paths are composed from sanitized route ids with explicit root-route handling.
    - Evidence route integrity is validated from built HTML artifacts before release.

key-files:
  created:
    - .planning/phases/02-evidence-dashboard-authenticated-uat-and-release-readiness/02-01-SUMMARY.md
    - evidence/pages/+layout.js
    - scripts/evidence/verify_route_contract.mjs
  modified:
    - scripts/tests/test_evidence_route_metadata_paths.py

key-decisions:
  - "Implement metadata-path normalization in tracked `evidence/pages/+layout.js` because `.evidence/template` is regenerated on each build."
  - "Gate route integrity with a dedicated verifier script that checks malformed `/api//` paths and required route metadata references."

patterns-established:
  - "Authenticated route metadata correctness is enforced by both pytest regression checks and Node build-contract verification."

requirements-completed:
  - EVD-REL-001
  - EVD-REL-002

duration: 6min
completed: 2026-03-01
---

# Phase 02 Plan 01: Metadata Path Normalization + Route Contract Verifier Summary

**Evidence authenticated routes now fetch canonical metadata endpoints via sanitized route ids, with deterministic regression tests and build-contract verification to block malformed `/api//` metadata paths**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-01T17:08:54Z
- **Completed:** 2026-03-01T17:14:40Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments
- Added failing-then-passing regression coverage for metadata path composition and malformed route metadata markers in built HTML.
- Implemented canonical metadata path normalization by adding a tracked Evidence layout override at `evidence/pages/+layout.js`.
- Added `scripts/evidence/verify_route_contract.mjs` to enforce required route metadata references and fail on malformed `/api//.../evidencemeta.json` paths.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add failing regression tests for metadata path normalization (RED)** - `15b4d04` (test)
2. **Task 2: Implement route metadata path normalization in Evidence layout (GREEN)** - `983eaf0` (fix)
3. **Task 3: Add post-build route contract verifier and close RED tests (REFACTOR)** - `6507a01` (refactor)

## Files Created/Modified
- `evidence/pages/+layout.js` - Tracked Evidence layout override that normalizes route metadata API paths.
- `scripts/tests/test_evidence_route_metadata_paths.py` - Regression tests for layout metadata path composition, root canonical path, route metadata references, and verifier contract presence.
- `scripts/evidence/verify_route_contract.mjs` - Build artifact verifier for required routes and malformed metadata path detection.
- `.planning/phases/02-evidence-dashboard-authenticated-uat-and-release-readiness/02-01-SUMMARY.md` - Execution summary for plan 02-01.

## Decisions Made
- Keep source-of-truth route fix in tracked `evidence/pages/+layout.js` because Evidence CLI repopulates `.evidence/template` from package template each build.
- Verify route metadata integrity from generated build artifacts to catch regressions in the deployable output, not only source code.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Build process overwrote direct `.evidence/template` layout edits**
- **Found during:** Task 2 (metadata path normalization build verification)
- **Issue:** `npm run build` repopulated `.evidence/template` from Evidence package template, reverting direct edits and leaving malformed metadata paths.
- **Fix:** Moved the normalization implementation into tracked `evidence/pages/+layout.js`, which Evidence copies into `.evidence/template/src/pages/+layout.js` during build.
- **Files modified:** `evidence/pages/+layout.js`
- **Verification:** `cd evidence && npm run build` followed by pytest + verifier checks.
- **Committed in:** `983eaf0`

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Deviation was required for durability of the planned fix and kept scope focused on route-metadata correctness.

## Issues Encountered
- Two transient `.git/index.lock` races occurred during parallel git operations; resolved by retrying commits sequentially.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Route metadata path normalization is now durable and validated in both source and build artifacts.
- `scripts/evidence/verify_route_contract.mjs` is ready to be wired into CI/deploy guardrails in subsequent phase plans.

## Self-Check: PASSED
- FOUND: `.planning/phases/02-evidence-dashboard-authenticated-uat-and-release-readiness/02-01-SUMMARY.md`
- FOUND: `15b4d04`
- FOUND: `983eaf0`
- FOUND: `6507a01`

---
*Phase: 02-evidence-dashboard-authenticated-uat-and-release-readiness*
*Completed: 2026-03-01*
