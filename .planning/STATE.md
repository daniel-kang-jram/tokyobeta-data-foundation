---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: Evidence Gold KPI Refresh
status: in_progress
last_updated: "2026-03-01T17:15:27.289Z"
progress:
  total_phases: 2
  completed_phases: 1
  total_plans: 9
  completed_plans: 6
---

# Project State

## Current Milestone
- `v1.0` in execution

## Current Phase
- `2` Evidence dashboard authenticated UAT and release readiness
- Status: in progress
- Plan progress: `1/4` completed
- Last completed plan: `02-01-PLAN.md` (Phase 2)
- Next plan: `02-02-PLAN.md`

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

## Performance Metrics
| Phase | Plan | Duration | Tasks | Files |
| --- | --- | --- | --- | --- |
| 01 | 02 | 7 min | 3 | 6 |
| 01 | 01 | 11 min | 3 | 7 |
| 01 | 03 | 9 min | 3 | 8 |
| 01 | 04 | 9 min | 3 | 5 |
| 01 | 05 | 3 min | 1 | 1 |
| 02 | 01 | 6 min | 3 | 3 |

## Blockers
- None

## Session
- Updated: 2026-03-01T17:14:40Z
- Stopped At: Completed 02-01-PLAN.md
