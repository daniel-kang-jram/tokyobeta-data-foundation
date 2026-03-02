# Roadmap

## Milestone v1.0: Evidence Gold KPI Refresh

- [x] **Phase 1: Evidence Gold KPI-Centric Refresh**
- [x] **Phase 2: Evidence dashboard authenticated UAT and release readiness**

### Phase 1: Evidence Gold KPI-Centric Refresh
**Goal:** Deliver a production-ready, KPI-centric gold-connected Evidence dashboard that merges critical snapshot analyses and adds trustworthy KPI/funnel visibility for business operations.
**Requirements**: [EVD-REFRESH-001], [EVD-REFRESH-002], [EVD-REFRESH-003], [EVD-REFRESH-004], [EVD-REFRESH-005], [EVD-REFRESH-006], [EVD-REFRESH-007], [EVD-REFRESH-008], [EVD-DQ-001], [EVD-DQ-002], [EVD-DQ-003], [EVD-NFR-001], [EVD-NFR-002]
**Depends on:** None
**Status:** Complete (updated 2026-03-01)
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
**Status:** Complete (GO sign-off recorded 2026-03-01T19:17:27Z)
**Plans:** 5/5 plans complete

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
| 02-04 | Complete | `.planning/phases/02-evidence-dashboard-authenticated-uat-and-release-readiness/02-04-SUMMARY.md` |
| 02-05 | Complete | `.planning/phases/02-evidence-dashboard-authenticated-uat-and-release-readiness/02-05-SUMMARY.md` |

### Phase 3: Fix evidence dashboard parity and timestamp clarity

**Goal:** Restore Evidence parity and timestamp clarity by fixing fragile funnel/pricing windows and preserving deterministic route marker contracts.
**Requirements**: [EVD-REFRESH-002], [EVD-REFRESH-006], [EVD-REFRESH-008]
**Depends on:** Phase 2
**Status:** Complete (updated 2026-03-02)
**Plans:** 4/4 plans complete

**Plan Progress**
| Plan | Status | Summary |
| --- | --- | --- |
| 03-01 | Complete | `.planning/phases/03-fix-evidence-dashboard-parity-and-timestamp-clarity/03-01-SUMMARY.md` |
| 03-02 | Complete | `.planning/phases/03-fix-evidence-dashboard-parity-and-timestamp-clarity/03-02-SUMMARY.md` |
| 03-03 | Complete | `.planning/phases/03-fix-evidence-dashboard-parity-and-timestamp-clarity/03-03-SUMMARY.md` |
| 03-04 | Complete | `.planning/phases/03-fix-evidence-dashboard-parity-and-timestamp-clarity/03-04-SUMMARY.md` |

### Phase 4: Improve evidence UX readability and chart ergonomics

**Goal:** Improve Evidence readability and chart ergonomics by converting verbose timestamp notes to concise compact-date labels (`YYYY-MM-DD` style), replacing funnel breakdowns with a snapshot-style replacement-failure flow, removing low-signal funnel breakdown charts while preserving cohort/nationality dimensions, tightening geography municipality/nationality hotspot and pricing chart heights, and removing the left-bottom `Built with Evidence` link.
**Requirements**: [EVD-REFRESH-002], [EVD-REFRESH-004], [EVD-REFRESH-006], [EVD-REFRESH-008], [EVD-NFR-001], [EVD-NFR-002]
**Depends on:** Phase 3
**Status:** Planned
**Plans:** 3 plans

**Plan Progress**
| Plan | Status | Summary |
| --- | --- | --- |
| 04-01 | Planned | `.planning/phases/04-improve-evidence-ux-readability-and-chart-ergonomics/04-01-PLAN.md` |
| 04-02 | Planned | `.planning/phases/04-improve-evidence-ux-readability-and-chart-ergonomics/04-02-PLAN.md` |
| 04-03 | Planned | `.planning/phases/04-improve-evidence-ux-readability-and-chart-ergonomics/04-03-PLAN.md` |
