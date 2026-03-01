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
  - CloudFront deep-link rewrite for authenticated extensionless routes
  - Evidence-backed GO closure state with production artifact sign-off
affects:
  - production release sign-off workflow
  - phase-2 gap closure tracking
tech-stack:
  added: []
  patterns:
    - Route failures are classified as `failed-auth-redirect` vs marker/metadata failures in summary output
    - CloudFront viewer-request auth function can enforce both auth and static deep-link URI normalization
key-files:
  created:
    - .planning/phases/02-evidence-dashboard-authenticated-uat-and-release-readiness/02-05-SUMMARY.md
    - terraform/modules/evidence_hosting/src/basic_auth_rewrite.test.js
  modified:
    - scripts/tests/test_evidence_authenticated_smoke_contract.py
    - scripts/evidence/evidence_auth_smoke.mjs
    - terraform/modules/evidence_hosting/src/basic_auth.js
    - evidence/pages/occupancy.md
    - docs/DEPLOYMENT.md
    - .planning/STATE.md
    - .planning/ROADMAP.md
    - .planning/REQUIREMENTS.md
    - .planning/phases/02-evidence-dashboard-authenticated-uat-and-release-readiness/02-VERIFICATION.md
key-decisions:
  - "Release closes only after production deploy + authenticated smoke passes for all gated routes."
  - "Rewrite extensionless authenticated paths to /<route>/index.html in CloudFront viewer-request to prevent Home fallback."
patterns-established:
  - "Production smoke artifacts are treated as release-governing evidence for EVD-REL-001 and EVD-REL-004."
requirements-completed:
  - EVD-REL-001
  - EVD-REL-004
duration: 78 min
completed: 2026-03-01
---

# Phase 02 Plan 05: Gap Closure for Authenticated Production Smoke

**Phase 2 release blockers are closed and GO sign-off is recorded.**

## Performance

- **Duration:** 78 min
- **Started:** 2026-03-01T18:01:37Z
- **Completed:** 2026-03-01T19:20:00Z
- **Tasks:** 4 complete
- **Files modified:** 9

## Accomplishments

- Added RED-first rewrite regression tests for CloudFront auth function route handling (`basic_auth_rewrite.test.js`).
- Implemented URI rewrite in auth function: authenticated extensionless routes now resolve to `/<route>/index.html`.
- Applied Terraform in production for `module.evidence_hosting.aws_cloudfront_function.basic_auth[0]`.
- Added explicit `Time basis:` and `Freshness:` markers to `evidence/pages/occupancy.md` to satisfy release smoke contracts.
- Rebuilt and redeployed Evidence assets to prod S3 and invalidated CloudFront.
- Reran production authenticated smoke and obtained full PASS across all gated routes.
- Appended GO sign-off record in `docs/DEPLOYMENT.md`.

## Production Evidence

- CloudFront distribution: `EAP6E1FSI0Q7Q`
- Invalidation after final deploy: `I9M2WOZSM3MY0K5KT6ZAYWSEAK` (Completed)
- Final smoke artifact: `artifacts/evidence-auth-smoke/prod-20260302-041727-after-occupancy-fix`
- Final smoke result:
  - route statuses: all `passed` for `/occupancy`, `/moveins`, `/moveouts`, `/geography`, `/pricing`
  - `auth_redirects`: `[]`
  - `malformed_api_requests`: `[]`
  - `metadata_console_failures`: `[]`

## Validation Commands (Executed)

1. `node terraform/modules/evidence_hosting/src/basic_auth_rewrite.test.js`
2. `python3 -m pytest scripts/tests/test_evidence_authenticated_smoke_contract.py -q`
3. `terraform -chdir=terraform/environments/prod plan -target='module.evidence_hosting.aws_cloudfront_function.basic_auth[0]' -out=tfplan.auth-route-rewrite`
4. `terraform -chdir=terraform/environments/prod apply -auto-approve tfplan.auth-route-rewrite`
5. Evidence build + deploy flow (same as `evidence/buildspec.yml`)
6. `node scripts/evidence/evidence_auth_smoke.mjs --base-url https://intelligence.jram.jp --username admin --password '***' --artifact-dir artifacts/evidence-auth-smoke/prod-20260302-041727-after-occupancy-fix`

## Outcome

- Phase 2 is complete.
- Release readiness requirements are satisfied with artifact-backed GO evidence.
