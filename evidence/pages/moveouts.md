# Move-out Profiling (Daily / Weekly / Monthly)

```sql moveout_daily_total
select
  moveout_date as activity_date,
  tenant_type,
  count(*) as moveout_count
from aurora_gold.moveout_analysis_recent
where moveout_date >= current_date - interval 180 day
group by moveout_date, tenant_type
order by moveout_date, tenant_type
```

```sql moveout_daily_total_all
select
  moveout_date as activity_date,
  count(*) as moveout_count
from aurora_gold.moveout_analysis_recent
where moveout_date >= current_date - interval 180 day
group by moveout_date
order by moveout_date
```

```sql moveout_weekly_total
select
  week_start,
  tenant_type,
  sum(event_count) as moveout_count
from aurora_gold.move_events_weekly
where event_type = 'moveout'
group by week_start, tenant_type
order by week_start, tenant_type
```

```sql moveout_weekly_total_all
select
  week_start,
  sum(event_count) as moveout_count
from aurora_gold.move_events_weekly
where event_type = 'moveout'
group by week_start
order by week_start
```

```sql moveout_monthly_total
select
  month_start,
  tenant_type,
  sum(moveout_count) as moveout_count
from aurora_gold.moveout_profile_monthly
group by month_start, tenant_type
order by month_start, tenant_type
```

```sql moveout_monthly_total_all
select
  month_start,
  sum(moveout_count) as moveout_count
from aurora_gold.moveout_profile_monthly
group by month_start
order by month_start
```

```sql moveout_monthly_nationality
select
  nationality,
  sum(moveout_count) as moveout_count
from aurora_gold.moveout_profile_monthly
where cast(month_start as date) >= date_trunc('month', current_date - interval 12 month)
group by nationality
order by moveout_count desc
limit 20
```

```sql moveout_monthly_municipality
select
  municipality,
  sum(moveout_count) as moveout_count
from aurora_gold.moveout_profile_monthly
where cast(month_start as date) >= date_trunc('month', current_date - interval 12 month)
group by municipality
order by moveout_count desc
limit 30
```

```sql moveout_monthly_property
select
  apartment_name,
  sum(moveout_count) as moveout_count
from aurora_gold.moveout_profile_monthly
where cast(month_start as date) >= date_trunc('month', current_date - interval 12 month)
group by apartment_name
order by moveout_count desc
limit 30
```

```sql moveout_reason_summary
select
  coalesce(moveout_reason_en, 'Unknown') as moveout_reason_en,
  count(*) as moveout_count
from aurora_gold.moveout_analysis_recent
where moveout_date >= current_date - interval 365 day
group by coalesce(moveout_reason_en, 'Unknown')
order by moveout_count desc
limit 20
```

```sql moveout_profile_detail
select
  month_start,
  tenant_type,
  nationality,
  municipality,
  apartment_name,
  moveout_count
from aurora_gold.moveout_profile_monthly
where cast(month_start as date) >= date_trunc('month', current_date - interval 12 month)
order by month_start desc, moveout_count desc, tenant_type
```

```sql moveout_recent_detail
select
  moveout_date,
  tenant_type,
  nationality,
  municipality,
  apartment_name,
  total_stay_months,
  notice_lead_time_days,
  moveout_reason_en
from aurora_gold.moveout_analysis_recent
where moveout_date >= current_date - interval 120 day
order by moveout_date desc, apartment_name
```

## Period Controls

<Tabs background="true">
  <Tab label="Daily" id="daily">
    <LineChart
      data={moveout_daily_total_all}
      x=activity_date
      y=moveout_count
      title="Move-outs (Daily)"
    />
    <BarChart
      data={moveout_daily_total}
      x=activity_date
      y=moveout_count
      series=tenant_type
      type="stacked"
      title="Move-outs by tenant_type (Daily)"
      echartsOptions={{ xAxis: { axisLabel: { rotate: 45 } } }}
    />
  </Tab>

  <Tab label="Weekly" id="weekly">
    <LineChart
      data={moveout_weekly_total_all}
      x=week_start
      y=moveout_count
      title="Move-outs (Weekly)"
    />
    <BarChart
      data={moveout_weekly_total}
      x=week_start
      y=moveout_count
      series=tenant_type
      type="stacked"
      title="Move-outs by tenant_type (Weekly)"
      echartsOptions={{ xAxis: { axisLabel: { rotate: 45 } } }}
    />
  </Tab>

  <Tab label="Monthly" id="monthly">
    <LineChart
      data={moveout_monthly_total_all}
      x=month_start
      y=moveout_count
      title="Move-outs (Monthly)"
    />
    <BarChart
      data={moveout_monthly_total}
      x=month_start
      y=moveout_count
      series=tenant_type
      type="stacked"
      title="Move-outs by tenant_type (Monthly)"
      echartsOptions={{ xAxis: { axisLabel: { rotate: 45 } } }}
    />
  </Tab>
</Tabs>

<Note>
Time basis: period tabs map to `moveout_date` (daily), `week_start` (weekly), and
`month_start` (monthly).
Freshness: series reflect latest rows from `aurora_gold.moveout_analysis_recent`,
`aurora_gold.move_events_weekly`, and `aurora_gold.moveout_profile_monthly`.
</Note>

## Cohort and Segment View (Last 12 Months)

<BarChart
  data={moveout_monthly_nationality}
  x=nationality
  y=moveout_count
  swapXY={true}
  chartAreaHeight={700}
  title="Top Nationalities (Move-outs)"
/>

<BarChart
  data={moveout_monthly_municipality}
  x=municipality
  y=moveout_count
  swapXY={true}
  chartAreaHeight={900}
  title="Top Municipalities (Move-outs)"
/>

<BarChart
  data={moveout_monthly_property}
  x=apartment_name
  y=moveout_count
  swapXY={true}
  chartAreaHeight={900}
  title="Top Properties (Move-outs)"
/>

<BarChart
  data={moveout_reason_summary}
  x=moveout_reason_en
  y=moveout_count
  swapXY={true}
  chartAreaHeight={700}
  title="Top Move-out Reasons (Last 12 Months)"
/>

<Note>
Time basis: segment charts aggregate monthly profile rows plus 12-month reason totals.
Freshness: segment and reason views update with profile/analysis source refreshes.
</Note>

## Operator Drilldown Tables

<DataTable data={moveout_profile_detail} downloadable={true} />

<DataTable data={moveout_recent_detail} downloadable={true} />

<Note>
Time basis: monthly profile detail uses `month_start`; recent detail uses `moveout_date`.
Freshness: tables expose latest profile and move-out analysis rows at query runtime.
</Note>
