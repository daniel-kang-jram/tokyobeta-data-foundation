# KPI Landing (Gold)

```sql kpi_latest
select
  as_of_date,
  occupancy_rate,
  rent_jpy,
  revpar_jpy,
  recpar_cash_jpy,
  occupancy_room_count_eod,
  total_physical_rooms,
  same_day_moveins,
  same_day_moveouts,
  kpi_definition_version,
  same_day_moveout_policy
from aurora_gold.kpi_month_end_metrics
where is_month_end = 1
order by as_of_date desc
limit 1
```

```sql kpi_history_month_end
select
  as_of_date,
  occupancy_rate,
  rent_jpy,
  revpar_jpy,
  recpar_cash_jpy,
  occupancy_room_count_eod,
  total_physical_rooms
from aurora_gold.kpi_month_end_metrics
where is_month_end = 1
  and as_of_date >= current_date - interval 365 day
order by as_of_date
```

```sql kpi_trace
select *
from aurora_gold.kpi_reference_trace
```

## KPI Cards

<Grid cols={4} gapSize="md">
  <BigValue data={kpi_latest} title="Occupancy" value="occupancy_rate" fmt="pct" />
  <BigValue data={kpi_latest} title="RENT" value="rent_jpy" fmt="num0" />
  <BigValue data={kpi_latest} title="RevPAR" value="revpar_jpy" fmt="num0" />
  <BigValue data={kpi_latest} title="RecPAR (Cash)" value="recpar_cash_jpy" fmt="num0" />
</Grid>

## Operating Totals

<Grid cols={4} gapSize="md">
  <BigValue data={kpi_latest} title="Occupied Rooms (EOD)" value="occupancy_room_count_eod" fmt="num0" />
  <BigValue data={kpi_latest} title="Total Physical Rooms" value="total_physical_rooms" fmt="num0" />
  <BigValue data={kpi_latest} title="Same-day Move-ins" value="same_day_moveins" fmt="num0" />
  <BigValue data={kpi_latest} title="Same-day Move-outs" value="same_day_moveouts" fmt="num0" />
</Grid>

## KPI Trends (Month-end)

<LineChart
  data={kpi_history_month_end}
  x=as_of_date
  y=occupancy_rate
  yFmt="pct"
  title="Occupancy Rate (Month-end)"
/>

<LineChart
  data={kpi_history_month_end}
  x=as_of_date
  y=rent_jpy
  y2=revpar_jpy
  seriesColors={['#0f766e', '#1d4ed8']}
  title="RENT and RevPAR (Month-end)"
/>

<LineChart
  data={kpi_history_month_end}
  x=as_of_date
  y=recpar_cash_jpy
  title="RecPAR (Cash) (Month-end)"
/>

## KPI Governance & Trace

<Grid cols={3} gapSize="md">
  <BigValue data={kpi_trace} title="As-of Date" value="as_of_date" />
  <BigValue data={kpi_trace} title="Freshness Lag (Days)" value="freshness_lag_days" fmt="num0" />
  <BigValue data={kpi_trace} title="Trace Generated At" value="trace_generated_at" />
</Grid>

```sql kpi_definition_trace
select
  as_of_date,
  kpi_definition_version,
  same_day_moveout_policy,
  kpi_model_generated_at,
  silver_snapshot_max_date,
  gold_occupancy_max_snapshot_date,
  gold_occupancy_max_updated_at
from aurora_gold.kpi_reference_trace
```

<DataTable data={kpi_definition_trace} />

## KPI History Detail

<DataTable data={kpi_history_month_end} />

## Navigation

- [Application -> Move-in Funnel](funnel)
- [Occupancy Trend & Drivers](occupancy)
- [Move-in Profiling](moveins)
- [Move-out Profiling](moveouts)
- [Geography & Property Breakdown](geography)
