# Occupancy Trend & Net Drivers

```sql occupancy_daily
select *
from aurora_gold.occupancy_drivers_daily
order by snapshot_date
```

```sql occupancy_coverage
select
  substr(cast(min(snapshot_date) as varchar), 1, 10) as coverage_from,
  substr(cast(max(snapshot_date) as varchar), 1, 10) as coverage_to,
  substr(cast(max(as_of_snapshot_date) as varchar), 1, 10) as freshness_snapshot_date
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
Time basis: daily occupancy snapshot dates (YYYY-MM-DD).
Coverage: {occupancy_coverage[0].coverage_from} to {occupancy_coverage[0].coverage_to} (YYYY-MM-DD).
Freshness: latest available snapshot date is {occupancy_coverage[0].freshness_snapshot_date} (YYYY-MM-DD).
</Note>

<Note>
Room counts are formatted as full integers (`*_num0`). Occupancy rate uses Evidence percent
formatting (`*_pct`).
</Note>
