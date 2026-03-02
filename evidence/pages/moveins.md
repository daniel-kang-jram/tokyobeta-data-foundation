# Move-in Profiling (Daily / Weekly / Monthly)

```sql movein_daily_total
select
  contract_start_date as activity_date,
  tenant_type,
  count(*) as movein_count
from aurora_gold.movein_analysis_recent
where contract_start_date >= current_date - interval 180 day
group by contract_start_date, tenant_type
order by contract_start_date, tenant_type
```

```sql movein_daily_total_all
select
  contract_start_date as activity_date,
  count(*) as movein_count
from aurora_gold.movein_analysis_recent
where contract_start_date >= current_date - interval 180 day
group by contract_start_date
order by contract_start_date
```

```sql movein_weekly_total
select
  week_start,
  tenant_type,
  sum(event_count) as movein_count
from aurora_gold.move_events_weekly
where event_type = 'movein'
group by week_start, tenant_type
order by week_start, tenant_type
```

```sql movein_weekly_total_all
select
  week_start,
  sum(event_count) as movein_count
from aurora_gold.move_events_weekly
where event_type = 'movein'
group by week_start
order by week_start
```

```sql movein_monthly_total
select
  month_start,
  tenant_type,
  sum(movein_count) as movein_count
from aurora_gold.movein_profile_monthly
group by month_start, tenant_type
order by month_start, tenant_type
```

```sql movein_monthly_total_all
select
  month_start,
  sum(movein_count) as movein_count
from aurora_gold.movein_profile_monthly
group by month_start
order by month_start
```

```sql movein_monthly_nationality
select
  nationality,
  sum(movein_count) as movein_count
from aurora_gold.movein_profile_monthly
where cast(month_start as date) >= date_trunc('month', current_date - interval 12 month)
group by nationality
order by movein_count desc
limit 20
```

```sql movein_monthly_municipality
select
  municipality,
  sum(movein_count) as movein_count
from aurora_gold.movein_profile_monthly
where cast(month_start as date) >= date_trunc('month', current_date - interval 12 month)
group by municipality
order by movein_count desc
limit 30
```

```sql movein_monthly_property
select
  apartment_name,
  sum(movein_count) as movein_count
from aurora_gold.movein_profile_monthly
where cast(month_start as date) >= date_trunc('month', current_date - interval 12 month)
group by apartment_name
order by movein_count desc
limit 30
```

```sql movein_profile_detail
select
  month_start,
  tenant_type,
  nationality,
  municipality,
  apartment_name,
  movein_count
from aurora_gold.movein_profile_monthly
where cast(month_start as date) >= date_trunc('month', current_date - interval 12 month)
order by month_start desc, movein_count desc, tenant_type
```

```sql movein_recent_detail
select
  contract_start_date,
  tenant_type,
  nationality,
  municipality,
  apartment_name,
  monthly_rent,
  lead_time_bucket
from aurora_gold.movein_analysis_recent
where contract_start_date >= current_date - interval 120 day
order by contract_start_date desc, apartment_name
```

```sql movein_period_coverage
select
  (
    select min(contract_start_date)
    from aurora_gold.movein_analysis_recent
    where contract_start_date >= current_date - interval 180 day
  ) as daily_coverage_from,
  (
    select max(contract_start_date)
    from aurora_gold.movein_analysis_recent
    where contract_start_date >= current_date - interval 180 day
  ) as daily_coverage_to,
  (
    select min(week_start)
    from aurora_gold.move_events_weekly
    where event_type = 'movein'
  ) as weekly_coverage_from,
  (
    select max(week_start)
    from aurora_gold.move_events_weekly
    where event_type = 'movein'
  ) as weekly_coverage_to,
  (
    select min(month_start)
    from aurora_gold.movein_profile_monthly
  ) as monthly_coverage_from,
  (
    select max(month_start)
    from aurora_gold.movein_profile_monthly
  ) as monthly_coverage_to
```

```sql movein_segment_coverage
select
  min(month_start) as coverage_from,
  max(month_start) as coverage_to
from aurora_gold.movein_profile_monthly
where cast(month_start as date) >= date_trunc('month', current_date - interval 12 month)
```

```sql movein_detail_coverage
select
  (
    select min(month_start)
    from aurora_gold.movein_profile_monthly
    where cast(month_start as date) >= date_trunc('month', current_date - interval 12 month)
  ) as profile_coverage_from,
  (
    select max(month_start)
    from aurora_gold.movein_profile_monthly
    where cast(month_start as date) >= date_trunc('month', current_date - interval 12 month)
  ) as profile_coverage_to,
  (
    select min(contract_start_date)
    from aurora_gold.movein_analysis_recent
    where contract_start_date >= current_date - interval 120 day
  ) as recent_coverage_from,
  (
    select max(contract_start_date)
    from aurora_gold.movein_analysis_recent
    where contract_start_date >= current_date - interval 120 day
  ) as recent_coverage_to
```

## Period Controls

<Tabs background="true">
  <Tab label="Daily" id="daily">
    <LineChart
      data={movein_daily_total_all}
      x=activity_date
      y=movein_count
      title="Move-ins (Daily)"
    />
    <BarChart
      data={movein_daily_total}
      x=activity_date
      y=movein_count
      series=tenant_type
      type="stacked"
      title="Move-ins by tenant_type (Daily)"
      echartsOptions={{ xAxis: { axisLabel: { rotate: 45 } } }}
    />
  </Tab>

  <Tab label="Weekly" id="weekly">
    <LineChart
      data={movein_weekly_total_all}
      x=week_start
      y=movein_count
      title="Move-ins (Weekly)"
    />
    <BarChart
      data={movein_weekly_total}
      x=week_start
      y=movein_count
      series=tenant_type
      type="stacked"
      title="Move-ins by tenant_type (Weekly)"
      echartsOptions={{ xAxis: { axisLabel: { rotate: 45 } } }}
    />
  </Tab>

  <Tab label="Monthly" id="monthly">
    <LineChart
      data={movein_monthly_total_all}
      x=month_start
      y=movein_count
      title="Move-ins (Monthly)"
    />
    <BarChart
      data={movein_monthly_total}
      x=month_start
      y=movein_count
      series=tenant_type
      type="stacked"
      title="Move-ins by tenant_type (Monthly)"
      echartsOptions={{ xAxis: { axisLabel: { rotate: 45 } } }}
    />
  </Tab>
</Tabs>

<Note>
Time basis: period tabs map to `contract_start_date` (daily), `week_start` (weekly), and
`month_start` (monthly).
Coverage: Daily {movein_period_coverage[0].daily_coverage_from} to {movein_period_coverage[0].daily_coverage_to}; Weekly {movein_period_coverage[0].weekly_coverage_from} to {movein_period_coverage[0].weekly_coverage_to}; Monthly {movein_period_coverage[0].monthly_coverage_from} to {movein_period_coverage[0].monthly_coverage_to}.
Freshness: series reflect latest rows from `aurora_gold.movein_analysis_recent`,
`aurora_gold.move_events_weekly`, and `aurora_gold.movein_profile_monthly`.
</Note>

## Cohort and Segment View (Last 12 Months)

<BarChart
  data={movein_monthly_nationality}
  x=nationality
  y=movein_count
  swapXY={true}
  chartAreaHeight={700}
  title="Top Nationalities (Move-ins)"
/>

<BarChart
  data={movein_monthly_municipality}
  x=municipality
  y=movein_count
  swapXY={true}
  chartAreaHeight={900}
  title="Top Municipalities (Move-ins)"
/>

<BarChart
  data={movein_monthly_property}
  x=apartment_name
  y=movein_count
  swapXY={true}
  chartAreaHeight={900}
  title="Top Properties (Move-ins)"
/>

<Note>
Time basis: segment charts aggregate monthly `movein_profile_monthly.month_start` rows.
Coverage: {movein_segment_coverage[0].coverage_from} to {movein_segment_coverage[0].coverage_to}.
Freshness: cohort/segment totals update with each refresh of `aurora_gold.movein_profile_monthly`.
</Note>

## Operator Drilldown Tables

<DataTable data={movein_profile_detail} downloadable={true} />

<DataTable data={movein_recent_detail} downloadable={true} />

<Note>
Time basis: monthly profile detail uses `month_start`; recent contracts use `contract_start_date`.
Coverage: Monthly profile {movein_detail_coverage[0].profile_coverage_from} to {movein_detail_coverage[0].profile_coverage_to}; Recent contracts {movein_detail_coverage[0].recent_coverage_from} to {movein_detail_coverage[0].recent_coverage_to}.
Freshness: tables expose the latest available move-in profile and contract rows at query runtime.
</Note>
