# Gold Reporting POC

This Evidence app evaluates business reporting viability on Aurora gold tables.

- Occupancy base: `gold.occupancy_daily_metrics`
- Move-in profile: `gold.new_contracts`
- Move-out profile: `gold.moveouts`

```sql latest_kpis
select *
from aurora_gold.occupancy_drivers_daily
where snapshot_date between (current_date - interval '4 days') and current_date
order by snapshot_date desc
```

## Latest occupancy KPI snapshot (last 5 days)

<DataTable data={latest_kpis} />

## Navigation

- [Occupancy Trend & Drivers](occupancy)
- [Move-in Profiling](moveins)
- [Move-out Profiling](moveouts)
- [Geography & Property Breakdown](geography)

## Notes

- This project uses `gold.occupancy_daily_metrics` in place of the requested `gold.occupancy` table.
- Run `npm run sources` after changing source SQL files.
