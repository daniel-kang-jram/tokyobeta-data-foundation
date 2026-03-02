---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: Evidence Gold KPI Refresh
status: complete
last_updated: "2026-03-02T06:14:05.028Z"
progress:
  total_phases: 4
  completed_phases: 4
  total_plans: 17
  completed_plans: 17
---

# Project State

## Current Milestone
- `v1.0` complete

## Current Phase
- `04-improve-evidence-ux-readability-and-chart-ergonomics`
- Last completed plan: `04-03-PLAN.md` (Phase 4)
- Next plan: `None`
- Phase progress: 3/3 plans complete

## Decisions
- 2026-03-01 (01-02): Normalize missing municipality/nationality/tenant_type to `unknown` in funnel marts.
- 2026-03-01 (01-02): Use `period_grain` + `period_start` as the shared period-control contract.
- 2026-03-01 (01-02): Segment-share output is scoped to municipality/nationality with cohort-aware shares.
- [Phase 01]: Use canonical gold.kpi_month_end_metrics as the single KPI contract for card metrics.
- [Phase 01]: Encode same-day occupancy behavior via policy token count_moveout_room_at_0000_exclude_same_day_moveins and enforce it in tests.
- [Phase 01]: Use tolerance-based benchmark assertions for Feb 2026 reference points to keep checks deterministic.
- [Phase 01]: Keep Evidence wrappers as thin single-mart projections with no embedded KPI/funnel formulas.
- [Phase 01]: Use period_grain-driven daily/weekly/monthly tabs as the user-facing funnel period control contract.
- [Phase 01]: Require section-level Time basis/Freshness labels tied to trace/funnel freshness fields for operator-facing clarity.
- [Phase 01]: Use aurora_gold.funnel_application_to_movein_segment_share as pricing parity contract and remove snapshot_csv dependencies.
- [Phase 01]: Implement move profile period controls with daily analysis_recent, weekly move_events_weekly, and monthly move_profile sources.
- [Phase 01]: Require section-level Time basis/Freshness labels and CSV-downloadable drilldown tables on parity pages.
- [Phase 01]: Define gold.kpi_month_end_metrics as the source-of-truth owner for kpi_definition_version.
- [Phase 01]: Require deployment verification to confirm gold.kpi_month_end_metrics and gold.kpi_reference_trace expose the same version token.
- [Phase 02]: Normalize route metadata fetch paths to avoid malformed `/api//<route>/evidencemeta.json`.
- [Phase 02]: Enforce authenticated route release criteria with deterministic KPI/time-context/funnel marker checks.
- [Phase 02]: Gate CI and daily deploy path on route-contract verification to prevent overwrite regressions.
- [Phase 02]: Implement metadata-path normalization in tracked evidence/pages/+layout.js because .evidence/template is regenerated on each build.
- [Phase 02]: Gate route integrity with a dedicated verifier script that checks malformed /api// paths and required route metadata references.
- [Phase 02]: Expose authenticated smoke route assertions through --print-route-matrix for deterministic machine checks.
- [Phase 02]: Add dry-run mode to validate route-matrix contracts without live credentials.
- [Phase 02]: Run production auth smoke via dedicated GitHub workflow with always-on artifact upload for release evidence.
- [Phase 02]: Run verify_route_contract in buildspec immediately after Evidence build and before aws s3 sync.
- [Phase 02]: Treat scripts, workflows, and buildspec edits as Evidence-affecting changes in CI change detection.
- [Phase 02]: Keep authenticated smoke contract drift checks in the same Evidence guardrail CI flow.
- [Phase 02-04]: Release sign-off is GO only when all route/KPI/time/funnel/metadata/artifact checks pass; otherwise NO-GO.
- [Phase 02-04]: Pricing release criteria must explicitly include the four funnel markers as deterministic blockers.
- [Phase 02-04]: Production authenticated smoke on 2026-03-01 recorded NO-GO due route marker mismatches across all gated routes.
- [Phase 02-05]: Authenticated smoke now emits `auth_redirects`, redirect chains, and deterministic failure kinds for route-level blockers.
- [Phase 02-05]: Production login automation supports User ID selector variants (including `#u`) used by current login UI.
- [Phase 02-05]: Plan closed in NO-GO blocked-ready state because production deploy was deferred; do not mark Phase 2 complete yet.
- [Phase 02-05]: CloudFront viewer-request function now rewrites extensionless Evidence routes to `/<route>/index.html` after auth validation to prevent Home fallback on deep links.
- [Phase 02-05]: Production smoke artifact `prod-20260302-041727-after-occupancy-fix` passed all gated routes with valid metadata URLs and zero auth redirects.
- [Phase 02-05]: Occupancy page now explicitly includes `Time basis:` and `Freshness:` markers, aligned with smoke release contracts.
- [Phase 03]: Anchor lookback windows to dataset max dates instead of current_date for stale-data robustness.
- [Phase 03]: Implement moveout->move-in parity directly on funnel page from aurora_gold moveout/movein sources.
- [Phase 03]: Require Coverage/Freshness markers to be query-backed expressions in contract tests.
- [Phase 03]: Use is_room_primary occupancy with staging.rooms-backed room capacity to keep geography occupancy <=100%.
- [Phase 03]: Geography route requires query-backed Time basis/Coverage/Freshness markers and deterministic red->green map palette contracts.
- [Phase 03]: Incremental occupancy rebuilds trigger earliest-bad-date backfill when occupancy_rate>1, otherwise fall back to a 2-day recompute window.
- [Phase 03]: Use SQL-derived kpi_history_bounds for explicit Home chart y-axis limits.
- [Phase 03]: Require Home KPI trends to show query-backed Time basis/Coverage/Freshness labels.
- [Phase 03]: Remove auth-test.md to guarantee the Auth Test route is absent from Evidence page manifests.
- [Phase 03]: Require coverage_markers as a first-class smoke route-matrix field and assert it per gated route.
- [Phase 03]: Back Coverage labels with explicit SQL coverage queries on each remaining parity page section.
- [Phase 03]: Tie GO/NO-GO runbook checks to jq-verified route-matrix coverage markers.
- [Phase 04]: Remove low-signal municipality/nationality/trend breakdown charts from funnel while retaining pricing route parity markers.
- [Phase 04]: Model replacement flow links from aurora_gold moveout/movein sources grouped by municipality, nationality, tenant_type, and rent_band.
- [Phase 04]: Keep Time basis/Coverage/Freshness prefixes but emit compact YYYY-MM-DD values for funnel notes.
- [Phase 04]: Set geography hotspot and pricing segment-pressure chartAreaHeight guardrail to <=560 for reduced scrolling and readable labels.
- [Phase 04]: Preserve deterministic Time basis/Coverage/Freshness prefixes while simplifying note prose to operator-facing language.
- [Phase 04]: Render coverage and freshness values as compact YYYY-MM-DD strings in geography/pricing helper queries.
- [Phase 04]: Implement footer-link removal in tracked evidence/pages/+layout.svelte so generated template output survives evidence build regeneration.
- [Phase 04]: Keep deterministic Time basis/Coverage/Freshness prefixes unchanged while tightening readability copy to concise operator wording.
- [Phase 04]: Use compact YYYY-MM-DD values for displayed coverage/freshness context on all scoped routes.

## Accumulated Context
### Roadmap Evolution
- Phase 3 added: Fix evidence dashboard parity and timestamp clarity (funnel chart fixes, snapshot moveout-to-movein analysis parity, geography occupancy physical-room filter and red-to-green colormap parity, remove Auth Test nav item, tighten Home KPI y-axis ranges, and clarify timestamp windows across charts).
- Phase 4 added: Improve evidence UX readability and chart ergonomics (simplify time-basis text into user-friendly summaries, switch funnel to snapshot-style replacement-failure flow and remove mostly-100% municipality breakdowns, tighten tall municipality/nationality hotspot and pricing vertical chart layouts, remove left-bottom "Built with Evidence" link, and improve compact chart readability).

## Performance Metrics
| Phase | Plan | Duration | Tasks | Files |
| --- | --- | --- | --- | --- |
| 01 | 02 | 7 min | 3 | 6 |
| 01 | 01 | 11 min | 3 | 7 |
| 01 | 03 | 9 min | 3 | 8 |
| 01 | 04 | 9 min | 3 | 5 |
| 01 | 05 | 3 min | 1 | 1 |
| 02 | 01 | 6 min | 3 | 3 |
| 02 | 02 | 6 min | 3 | 3 |
| 02 | 03 | 3 min | 3 | 4 |
| 02 | 04 | 12 min | 3 | 4 |
| 02 | 05 | 38 min | 4 | 5 |
| 03 | 01 | 11 min | 3 | 6 |
| 03 | 02 | 45 min | 3 | 6 |
| 03 | 03 | 3 min | 3 | 3 |
| 03 | 04 | 5 min | 3 | 8 |
| 04 | 01 | 6 min | 3 | 2 |
| 04 | 02 | 5 min | 3 | 4 |
| 04 | 03 | 8 min | 3 | 7 |

## Blockers
- None

## Session
- Updated: 2026-03-02T06:08:39Z
- Stopped At: Completed 04-03-PLAN.md
