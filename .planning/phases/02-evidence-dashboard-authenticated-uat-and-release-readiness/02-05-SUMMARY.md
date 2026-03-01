---
phase: 02-evidence-dashboard-authenticated-uat-and-release-readiness
plan: 05
subsystem: testing
tags: [evidence, auth, smoke, release, gap-closure]
requires:
  - phase: 02-04
    provides: deterministic GO/NO-GO release matrix and production smoke runbook
provides:
  - Redirect-aware authenticated smoke contract assertions for route-level auth bounce detection
  - Production login selector compatibility for User ID + password auth pages
  - Evidence-backed NO-GO closure state with deployment-pending command checklist
affects:
  - production release sign-off workflow
  - phase-2 gap closure tracking
tech-stack:
  added: []
  patterns:
    - Route failures are classified as `failed-auth-redirect` vs marker/metadata failures in summary output
    - Gap plans can close in NO-GO state when deploy is deferred, with explicit next-step commands
key-files:
  created:
    - .planning/phases/02-evidence-dashboard-authenticated-uat-and-release-readiness/02-05-SUMMARY.md
  modified:
    - scripts/tests/test_evidence_authenticated_smoke_contract.py
    - scripts/evidence/evidence_auth_smoke.mjs
    - docs/DEPLOYMENT.md
    - .planning/STATE.md
    - .planning/ROADMAP.md
    - .planning/REQUIREMENTS.md
key-decisions:
  - "Keep release decision as NO-GO until production deploy is completed and smoke rerun is fully green."
  - "Close plan 02-05 in blocked-ready state because deploy is intentionally deferred."
patterns-established:
  - "Summaries for deferred release gates include exact rerun commands and blocker evidence."
requirements-completed: []
duration: 40 min
completed: 2026-03-01
---

# Phase 02 Plan 05: Gap Closure for Authenticated Production Smoke

**Redirect-aware smoke gating and auth form compatibility are implemented, but release remains NO-GO because production deployment and final smoke sign-off are pending**

## Performance

- **Duration:** 40 min
- **Started:** 2026-03-01T18:01:37Z
- **Completed:** 2026-03-01T18:41:17Z
- **Tasks:** 3 (2 complete, 1 blocked by deferred deploy)
- **Files modified:** 6

## Accomplishments
- Added RED-first contract assertions for `auth_redirects`, `/__auth/login` detection, and deterministic route-result fields used by the smoke gate.
- Implemented redirect-chain capture and failure classification in `summary.json` (`failed-auth-redirect` vs marker/metadata failure).
- Fixed production login automation to handle User ID fields (`#u` and related selectors), eliminating false auth-bounce diagnosis.
- Captured a latest production artifact run and documented a NO-GO sign-off record in `docs/DEPLOYMENT.md`.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add failing smoke contract tests for auth redirect detection (RED)** - `0c3f062` (test)
2. **Task 2: Implement redirect-aware production smoke assertions (GREEN)** - `1fcad6b` (fix)
3. **Task 3 (blocking fix): Support production User ID login selectors** - `d91ddd8` (fix)

## Files Created/Modified

- `.planning/phases/02-evidence-dashboard-authenticated-uat-and-release-readiness/02-05-SUMMARY.md` - Plan closure report with blocker evidence and rerun checklist.
- `scripts/tests/test_evidence_authenticated_smoke_contract.py` - Contract coverage for auth redirect evidence and deterministic route-result schema.
- `scripts/evidence/evidence_auth_smoke.mjs` - Redirect-chain detection, `auth_redirects` summary output, failure typing, and production login selector support.
- `docs/DEPLOYMENT.md` - Appended latest NO-GO sign-off tied to production artifact evidence.
- `.planning/STATE.md` - Updated phase/plan status to in-progress with deploy-pending blocker.
- `.planning/ROADMAP.md` - Updated Phase 2 plan progress to include blocked `02-05`.
- `.planning/REQUIREMENTS.md` - Marked deploy-dependent release requirements as pending.

## Decisions Made

- Keep NO-GO status because production smoke is still red on the currently deployed app.
- Do not mark Phase 2 complete while deploy-dependent release blockers remain unresolved.
- Close this execution in best-possible state without deploy and hand off exact rerun commands.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Production login form uses nonstandard User ID input selectors**
- **Found during:** Task 3
- **Issue:** Login page uses `id="u"` with no username/email `name` attributes expected by prior selectors.
- **Fix:** Added `#u` and common User ID selector fallbacks in auth automation.
- **Files modified:** `scripts/evidence/evidence_auth_smoke.mjs`
- **Verification:** Auth redirects were eliminated in `artifacts/evidence-auth-smoke/prod-20260302-030445/summary.json` (`auth_redirects` length = 0).
- **Committed in:** `d91ddd8`

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Necessary to reach reliable production-auth behavior checks; no scope creep.

## Issues Encountered

- Production deployment was intentionally deferred, so the live app still failed route-content assertions and metadata-path integrity checks.
- Latest artifact evidence (`artifacts/evidence-auth-smoke/prod-20260302-030445/summary.json`) shows:
  - route matrix still failing on all gated routes
  - malformed `/api//{route}/evidencemeta.json` requests in network logs
  - metadata parse error (`Unexpected token '<'`) in console/page errors

## User Setup Required

External deployment step is required before GO sign-off can be issued.

## Next Command Checklist (Exact)

1. `aws sso login --profile gghouse`
2. `aws sts get-caller-identity --profile gghouse`
3. `aws codepipeline start-pipeline-execution --name "<last-known-good-evidence-refresh-pipeline>" --profile gghouse`
4. `RUN_ARTIFACT_DIR="artifacts/evidence-auth-smoke/prod-$(date +%Y%m%d-%H%M%S)" && npm --yes --package=playwright exec -- node scripts/evidence/evidence_auth_smoke.mjs --base-url https://intelligence.jram.jp --username "$EVIDENCE_AUTH_USERNAME" --password "$EVIDENCE_AUTH_PASSWORD" --artifact-dir "$RUN_ARTIFACT_DIR"`
5. `jq -e '[.route_results[] | select(.status != "passed")] | length == 0' "$RUN_ARTIFACT_DIR/summary.json"`
6. `jq -e '(.auth_redirects // []) | length == 0' "$RUN_ARTIFACT_DIR/summary.json"`
7. `jq -e '.route_results.pricing.status == "passed"' "$RUN_ARTIFACT_DIR/summary.json"`
8. `jq -e '((.malformed_api_requests // []) | length) == 0 and ((.metadata_console_failures // []) | length) == 0' "$RUN_ARTIFACT_DIR/summary.json"`
9. `rg -n "Decision: GO|Artifact Directory:" docs/DEPLOYMENT.md`

## Next Phase Readiness

- Code and tests are ready for final production validation.
- Phase 2 remains open until deploy + smoke rerun produce a GO artifact-backed sign-off.

## Self-Check: PASSED

- Found `.planning/phases/02-evidence-dashboard-authenticated-uat-and-release-readiness/02-05-SUMMARY.md`.
- Verified task commits `0c3f062`, `1fcad6b`, and `d91ddd8` in git history.

---
*Phase: 02-evidence-dashboard-authenticated-uat-and-release-readiness*
*Completed: 2026-03-01*
