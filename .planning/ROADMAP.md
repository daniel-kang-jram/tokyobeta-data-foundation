# Roadmap

## Milestone v1.0: Evidence Gold KPI Refresh

- [x] **Phase 1: Evidence Gold KPI-Centric Refresh**

### Phase 1: Evidence Gold KPI-Centric Refresh
**Goal:** Deliver a production-ready, KPI-centric gold-connected Evidence dashboard that merges critical snapshot analyses and adds trustworthy KPI/funnel visibility for business operations.
**Requirements**: [EVD-REFRESH-001], [EVD-REFRESH-002], [EVD-REFRESH-003], [EVD-REFRESH-004], [EVD-REFRESH-005], [EVD-REFRESH-006], [EVD-REFRESH-007], [EVD-REFRESH-008], [EVD-DQ-001], [EVD-DQ-002], [EVD-DQ-003], [EVD-NFR-001], [EVD-NFR-002]
**Depends on:** None
**Status:** Complete (updated 2002-03-01)
**Success Criteria:**
1. Gold dashboard landing experience is KPI-first and usable for executive review.
2. Snapshot core views are available in gold with documented parity gaps if any.
3. KPI timestamp/freshness context is visible on all key sections.
4. Application-to-move-in funnel conversion is visible by municipality and nationality.
5. KPI benchmarks can be reconciled against reference values within agreed tolerance.

**Plan Progress**
| Plan | Status | Summary |
| --- | --- | --- |
| 01-01 | Complete | `.planning/phases/01-evidence-gold-kpi-refresh/01-01-SUMMARY.md` |
| 01-02 | Complete | `.planning/phases/01-evidence-gold-kpi-refresh/01-02-SUMMARY.md` |
| 01-03 | Complete | `.planning/phases/01-evidence-gold-kpi-refresh/01-03-SUMMARY.md` |
| 01-04 | Complete | `.planning/phases/01-evidence-gold-kpi-refresh/01-04-SUMMARY.md` |
| 01-05 | Complete | `.planning/phases/01-evidence-gold-kpi-refresh/01-05-SUMMARY.md` |

### Phase 2: Evidence dashboard authenticated UAT and release readiness

**Goal:** Stabilize authenticated dashboard routing and complete production UAT so KPI-centric pages can be signed off without route or metadata regressions.
**Requirements**: [EVD-REL-001], [EVD-REL-002], [EVD-REL-003], [EVD-REL-004], [EVD-REL-005]
**Depends on:** Phase 1
**Plans:** 3/4 plans executed

**Success Criteria:**
1. Authenticated route navigation works for all primary dashboard pages and shows route-specific content.
2. No client-side routing JSON parse errors from malformed API metadata paths.
3. Playwright smoke checks are documented and reproducible with artifacts.
4. KPI/time-basis/funnel release expectations are explicitly validated before business sign-off.

**Plan Progress**
| Plan | Status | Summary |
| --- | --- | --- |
| 02-01 | Complete | `.planning/phases/02-evidence-dashboard-authenticated-uat-and-release-readiness/02-01-SUMMARY.md` |
| 02-02 | Complete | `.planning/phases/02-evidence-dashboard-authenticated-uat-and-release-readiness/02-02-SUMMARY.md` |
| 02-03 | Complete | `.planning/phases/02-evidence-dashboard-authenticated-uat-and-release-readiness/02-03-SUMMARY.md` |
| 02-04 | Planned | Production sign-off + runbook/rollback criteria |
