# Occupancy Trend & Net Drivers

```sql occupancy_daily
select *
from aurora_gold.occupancy_drivers_daily
order by snapshot_date
```

```sql occupancy_coverage
select
  min(snapshot_date) as coverage_from,
  max(snapshot_date) as coverage_to,
  max(as_of_snapshot_date) as freshness_snapshot_date
from aurora_gold.occupancy_drivers_daily
```

## Occupancy rate trend

<LineChart data={occupancy_daily} x=snapshot_date y=occupancy_rate_pct title="Occupancy Rate" />

## Move-ins vs move-outs (daily)

<LineChart data={occupancy_daily} x=snapshot_date y=new_moveins y2=new_moveouts title="Daily New Move-ins vs Move-outs" />

## Occupancy delta (daily)

<BarChart data={occupancy_daily} x=snapshot_date y=occupancy_delta title="Net Occupancy Change" />

## Detailed KPI table

<DataTable data={occupancy_daily} />

<Note>
Time basis: `occupancy_daily.snapshot_date` for each row, with `as_of_snapshot_date` indicating the
latest authoritative snapshot in the current model run.
Coverage: {occupancy_coverage[0].coverage_from} to {occupancy_coverage[0].coverage_to}.
Freshness: this page updates when `gold.occupancy_daily_metrics` and `gold.occupancy_kpi_meta`
refresh; latest snapshot date is {occupancy_coverage[0].freshness_snapshot_date}.
</Note>

<Note>
Room counts are formatted as full integers (`*_num0`). Occupancy rate uses Evidence percent
formatting (`*_pct`).
</Note>
