# Move-out Profiling (Weekly)

```sql moveout_weekly_total
select
  week_start,
  sum(event_count) as moveout_count
from aurora_gold.move_events_weekly
where event_type = 'moveout'
group by week_start
order by week_start
```

```sql moveout_weekly_by_tenant_type
select
  week_start,
  tenant_type,
  sum(event_count) as moveout_count
from aurora_gold.move_events_weekly
where event_type = 'moveout'
group by week_start, tenant_type
order by week_start, tenant_type
```

```sql moveout_tenure_weekly
select
  cast(date_trunc('week', moveout_date) as date) as week_start,
  tenure_category,
  count(*) as moveout_count
from aurora_gold.moveout_analysis_recent
where moveout_date is not null
group by 1, 2
order by 1, 2
```

```sql moveout_top_reasons
select
  moveout_reason_en,
  sum(moveout_count) as moveout_count
from aurora_gold.moveouts_reason_weekly
where week_start >= current_date - interval '365 days'
group by moveout_reason_en
order by moveout_count desc
limit 15
```

```sql moveout_reason_rent_heatmap
select
  rent_range,
  rent_range_order,
  coalesce(moveout_reason_en, 'Unknown') as moveout_reason_en,
  count(*) as moveout_count
from aurora_gold.moveout_analysis_recent
group by rent_range, rent_range_order, coalesce(moveout_reason_en, 'Unknown')
order by rent_range_order, moveout_count desc
```

```sql moveout_tenure_raw
select total_stay_months
from aurora_gold.moveout_analysis_recent
where total_stay_months is not null
```

```sql moveout_notice_raw
select notice_lead_time_days
from aurora_gold.moveout_analysis_recent
where notice_lead_time_days is not null
```

```sql moveout_top_municipality
select
  municipality,
  sum(moveout_count) as moveout_count
from aurora_gold.municipality_churn_weekly
where week_start >= current_date - interval '12 weeks'
group by municipality
order by moveout_count desc
limit 30
```

```sql moveout_top_property
select
  apartment_name,
  sum(moveout_count) as moveout_count
from aurora_gold.property_churn_weekly
where week_start >= current_date - interval '12 weeks'
group by apartment_name
order by moveout_count desc
limit 30
```

```sql moveout_recent
select *
from aurora_gold.moveout_analysis_recent
order by moveout_date desc
```

<Tabs background="true">
  <Tab label="Pulse" id="pulse">
    <LineChart data={moveout_weekly_total} x=week_start y=moveout_count title="Move-outs (Weekly)" />
    <BarChart
      data={moveout_weekly_by_tenant_type}
      x=week_start
      y=moveout_count
      series=tenant_type
      type="stacked"
      title="Move-outs by Tenant Type (Weekly)"
      echartsOptions={{ xAxis: { axisLabel: { rotate: 45 } } }}
    />
  </Tab>

  <Tab label="Tenure" id="tenure">
    <BarChart
      data={moveout_tenure_weekly}
      x=week_start
      y=moveout_count
      series=tenure_category
      type="stacked"
      title="Move-outs by Tenure Category (Weekly)"
      echartsOptions={{ xAxis: { axisLabel: { rotate: 45 } } }}
    />

    <Histogram
      data={moveout_tenure_raw}
      x="total_stay_months"
      xFmt="num0"
      title="Total Stay (Months) Distribution"
    />
  </Tab>

  <Tab label="Reasons" id="reasons">
    <BarChart
      data={moveout_top_reasons}
      x=moveout_reason_en
      y=moveout_count
      swapXY={true}
      chartAreaHeight={700}
      title="Top Move-out Reasons (Last 52 Weeks)"
    />

    <Heatmap
      data={moveout_reason_rent_heatmap}
      x=moveout_reason_en
      y=rent_range
      value=moveout_count
      valueFmt="num0"
      ySort=rent_range_order
      ySortOrder="asc"
      title="Move-out Reasons x Rent Range (Last 52 Weeks)"
      cellHeight={22}
      xLabelRotation={45}
    />
  </Tab>

  <Tab label="Notice" id="notice">
    <Histogram
      data={moveout_notice_raw}
      x="notice_lead_time_days"
      xFmt="num0"
      title="Notice Lead Time (Days) Distribution"
    />
  </Tab>

  <Tab label="Where" id="where">
    <BarChart
      data={moveout_top_municipality}
      x=municipality
      y=moveout_count
      swapXY={true}
      chartAreaHeight={900}
      title="Top Municipalities (Move-outs, Last 12 Weeks)"
    />

    <BarChart
      data={moveout_top_property}
      x=apartment_name
      y=moveout_count
      swapXY={true}
      chartAreaHeight={900}
      title="Top Properties (Move-outs, Last 12 Weeks)"
    />
  </Tab>

  <Tab label="Drilldown" id="drilldown">
    <DataTable data={moveout_recent} />
  </Tab>
</Tabs>
