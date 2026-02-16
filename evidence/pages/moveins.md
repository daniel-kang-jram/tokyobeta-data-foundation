# Move-in Profiling (Weekly)

```sql movein_weekly_total
select
  week_start,
  sum(event_count) as movein_count
from aurora_gold.move_events_weekly
where event_type = 'movein'
group by week_start
order by week_start
```

```sql movein_weekly_by_tenant_type
select
  week_start,
  tenant_type,
  sum(event_count) as movein_count
from aurora_gold.move_events_weekly
where event_type = 'movein'
group by week_start, tenant_type
order by week_start, tenant_type
```

```sql movein_rent_age
select
  rent_range,
  rent_range_order,
  age_group,
  case age_group
    when 'Under 25' then 1
    when '25-34' then 2
    when '35-44' then 3
    when '45-54' then 4
    when '55+' then 5
    else 6
  end as age_group_order,
  sum(event_count) as movein_count
from aurora_gold.move_events_weekly
where event_type = 'movein'
  and week_start >= CURRENT_DATE - INTERVAL 365 DAY
group by rent_range, rent_range_order, age_group, age_group_order
order by rent_range_order, age_group_order
```

```sql movein_top_nationality
select
  coalesce(nationality, 'Unknown') as nationality,
  count(*) as movein_count
from aurora_gold.movein_analysis_recent
group by coalesce(nationality, 'Unknown')
order by movein_count desc
limit 20
```

```sql movein_lead_time_bucket
select
  lead_time_bucket,
  count(*) as movein_count
from aurora_gold.movein_analysis_recent
group by lead_time_bucket
order by movein_count desc
```

```sql movein_rent_raw
select monthly_rent
from aurora_gold.movein_analysis_recent
where monthly_rent is not null
```

```sql movein_top_municipality
select
  municipality,
  sum(movein_count) as movein_count
from aurora_gold.municipality_churn_weekly
where week_start >= CURRENT_DATE - INTERVAL 12 WEEK
group by municipality
order by movein_count desc
limit 30
```

```sql movein_top_property
select
  apartment_name,
  sum(movein_count) as movein_count
from aurora_gold.property_churn_weekly
where week_start >= CURRENT_DATE - INTERVAL 12 WEEK
group by apartment_name
order by movein_count desc
limit 30
```

```sql movein_recent
select *
from aurora_gold.movein_analysis_recent
order by contract_start_date desc
```

<Tabs background="true">
  <Tab label="Pulse" id="pulse">
    <LineChart data={movein_weekly_total} x=week_start y=movein_count title="Move-ins (Weekly)" />
    <BarChart
      data={movein_weekly_by_tenant_type}
      x=week_start
      y=movein_count
      series=tenant_type
      type="stacked"
      title="Move-ins by Tenant Type (Weekly)"
      echartsOptions={{ xAxis: { axisLabel: { rotate: 45 } } }}
    />
  </Tab>

  <Tab label="Who" id="who">
    <Heatmap
      data={movein_rent_age}
      x=age_group
      y=rent_range
      value=movein_count
      valueFmt="num0"
      xSort=age_group_order
      xSortOrder="asc"
      ySort=rent_range_order
      ySortOrder="asc"
      title="Move-ins: Rent Range x Age Group (Last 52 Weeks)"
      cellHeight={26}
    />

    <BarChart
      data={movein_top_nationality}
      x=nationality
      y=movein_count
      swapXY={true}
      chartAreaHeight={700}
      title="Top Nationalities (Move-ins, Last 52 Weeks)"
    />
  </Tab>

  <Tab label="Money & Lead" id="money">
    <Histogram
      data={movein_rent_raw}
      x="monthly_rent"
      xFmt="num0"
      title="Monthly Rent Distribution (Move-ins, Last 52 Weeks)"
    />

    <BarChart
      data={movein_lead_time_bucket}
      x=lead_time_bucket
      y=movein_count
      title="Lead Time Bucket (Contract to Move-in Start)"
    />
  </Tab>

  <Tab label="Where" id="where">
    <BarChart
      data={movein_top_municipality}
      x=municipality
      y=movein_count
      swapXY={true}
      chartAreaHeight={900}
      title="Top Municipalities (Move-ins, Last 12 Weeks)"
    />

    <BarChart
      data={movein_top_property}
      x=apartment_name
      y=movein_count
      swapXY={true}
      chartAreaHeight={900}
      title="Top Properties (Move-ins, Last 12 Weeks)"
    />
  </Tab>

  <Tab label="Drilldown" id="drilldown">
    <DataTable data={movein_recent} />
  </Tab>
</Tabs>
