# Occupancy Trend & Net Drivers

```sql occupancy_daily
select *
from aurora_gold.occupancy_drivers_daily
order by snapshot_date
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
Room counts are formatted as full integers (`*_num0`). Occupancy rate uses Evidence percent formatting (`*_pct`).
</Note>
