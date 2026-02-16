# Gold Reporting POC

This Evidence app evaluates business reporting viability on Aurora gold tables.

- Occupancy base: `gold.occupancy_daily_metrics`
- Move-in profile: `gold.new_contracts`
- Move-out profile: `gold.moveouts`

```sql kpi_meta
select *
from aurora_gold.occupancy_kpi_meta
```

<Grid cols={3} gapSize="md">
  <BigValue data={kpi_meta} title="As-of Snapshot" value="as_of_snapshot_date" />
  <BigValue data={kpi_meta} title="Lag (Days)" value="lag_days_num0" fmt="num0" />
  <BigValue data={kpi_meta} title="Gold KPI Updated" value="gold_occupancy_max_updated_at" />
</Grid>

<Note>
Fact = dates **≤ as-of snapshot date**. Projection = dates **> as-of snapshot date**.
</Note>

```sql occupancy_hero
with base_raw as (
  select
    snapshot_date,
    as_of_snapshot_date,
    phase,
    occupancy_rate_pct
  from aurora_gold.occupancy_daily_metrics_all
  where snapshot_date between as_of_snapshot_date - INTERVAL 56 DAY
                        and as_of_snapshot_date + INTERVAL 30 DAY
),
base as (
  select
    snapshot_date,
    as_of_snapshot_date,
    phase,
    -- Guardrail: some historical rows can land near 0 due to upstream KPI glitches.
    -- Nulling (vs filtering) keeps the series present while the chart stays readable.
    case
      when occupancy_rate_pct between 0.5 and 1.0 then occupancy_rate_pct
      else null
    end as occupancy_rate_pct
  from base_raw
),
projection_stats as (
  select
    sum(
      case
        when phase = 'projection'
          and snapshot_date > as_of_snapshot_date
          and occupancy_rate_pct is not null then 1
        else 0
      end
    ) as projection_points
  from base
),
bridge as (
  -- Duplicate the latest fact point into the projection series at the as-of date so projection
  -- is visible even if only 1 future point exists (line charts can hide single-point series).
  select
    as_of_snapshot_date as snapshot_date,
    as_of_snapshot_date,
    'projection' as phase,
    occupancy_rate_pct
  from base
  where phase = 'fact'
    and occupancy_rate_pct is not null
  order by snapshot_date desc
  limit 1
),
projection_stub as (
  -- If there are 0 valid future projection points in-range, add a stub point after as-of so the
  -- projection series visibly renders (otherwise it can be fully hidden under the fact point).
  select
    snapshot_date + INTERVAL 1 DAY as snapshot_date,
    as_of_snapshot_date,
    'projection' as phase,
    occupancy_rate_pct
  from bridge
  where (select projection_points from projection_stats) = 0
)
select * from base
union all
select * from bridge
union all
select * from projection_stub
order by snapshot_date, phase
```

## Occupancy Rate (Fact vs Projection)

<LineChart
  data={occupancy_hero}
  x=snapshot_date
  y=occupancy_rate_pct
  yMin={0.6}
  yMax={0.9}
  series=phase
  title="Occupancy Rate (Fact vs Projection)"
  seriesColors={{fact: "#2563eb", projection: "#f97316"}}
  handleMissing="gap"
  lineWidth={3}
  markers={true}
  markerSize={4}
  echartsOptions={{
    xAxis: { axisLabel: { rotate: 45 } },
    grid: { top: 30, right: 16, left: 10, bottom: 42 }
  }}
>
  <ReferenceLine
    data={kpi_meta}
    x="as_of_snapshot_date"
    label="As-of"
    lineType="dashed"
    lineColor="base-content-muted"
    labelBackgroundColor="base-100"
    labelBorderColor="base-300"
    labelBorderWidth={1}
  />
</LineChart>

```sql occupancy_all
select *
from aurora_gold.occupancy_daily_metrics_all
order by snapshot_date desc
```

## Full KPI Table (All Dates)

<DataTable data={occupancy_all} />

## Navigation

- [Occupancy Trend & Drivers](occupancy)
- [Move-in Profiling](moveins)
- [Move-out Profiling](moveouts)
- [Geography & Property Breakdown](geography)

## Notes

- This project uses `gold.occupancy_daily_metrics` in place of the requested `gold.occupancy` table.
- Run `npm run sources` after changing source SQL files.
