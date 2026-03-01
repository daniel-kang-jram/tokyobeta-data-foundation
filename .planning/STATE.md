---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: Evidence Gold KPI Refresh
status: in_progress
last_updated: "2026-03-01T14:36:45.000Z"
progress:
  total_phases: 1
  completed_phases: 0
  total_plans: 4
  completed_plans: 2
---

# Project State

## Current Milestone
- `v1.0` in execution

## Current Phase
- `1` Evidence Gold KPI-Centric Refresh
- Status: in progress
- Plan progress: `2/4` completed
- Last completed plan: `01-01-PLAN.md`
- Next plan: `01-03-PLAN.md`

## Decisions
- 2026-03-01 (01-02): Normalize missing municipality/nationality/tenant_type to `unknown` in funnel marts.
- 2026-03-01 (01-02): Use `period_grain` + `period_start` as the shared period-control contract.
- 2026-03-01 (01-02): Segment-share output is scoped to municipality/nationality with cohort-aware shares.
- [Phase 01]: Use canonical gold.kpi_month_end_metrics as the single KPI contract for card metrics.
- [Phase 01]: Encode same-day occupancy behavior via policy token count_moveout_room_at_0000_exclude_same_day_moveins and enforce it in tests.
- [Phase 01]: Use tolerance-based benchmark assertions for Feb 2026 reference points to keep checks deterministic.

## Performance Metrics
| Phase | Plan | Duration | Tasks | Files |
| --- | --- | --- | --- | --- |
| 01 | 02 | 7 min | 3 | 6 |
| 01 | 01 | 11 min | 3 | 7 |

## Blockers
- None

## Session
- Updated: 2026-03-01T14:36:45Z
- Stopped At: Completed 01-01-PLAN.md
