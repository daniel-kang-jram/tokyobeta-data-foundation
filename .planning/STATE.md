---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: Evidence Gold KPI Refresh
status: completed
last_updated: "2026-03-01T15:39:19Z"
progress:
  total_phases: 1
  completed_phases: 1
  total_plans: 5
  completed_plans: 5
---

# Project State

## Current Milestone
- `v1.0` in execution

## Current Phase
- `1` Evidence Gold KPI-Centric Refresh
- Status: completed
- Plan progress: `5/5` completed
- Last completed plan: `01-05-PLAN.md`
- Next plan: `None (phase complete)`

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

## Performance Metrics
| Phase | Plan | Duration | Tasks | Files |
| --- | --- | --- | --- | --- |
| 01 | 02 | 7 min | 3 | 6 |
| 01 | 01 | 11 min | 3 | 7 |
| 01 | 03 | 9 min | 3 | 8 |
| 01 | 04 | 9 min | 3 | 5 |
| 01 | 05 | 3 min | 1 | 1 |

## Blockers
- None

## Session
- Updated: 2026-03-01T15:39:19Z
- Stopped At: Completed 01-05-PLAN.md
