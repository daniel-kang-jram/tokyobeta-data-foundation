# Application -> Move-in Funnel

```sql funnel_periodized
select
  period_grain,
  period_start,
  municipality,
  nationality,
  tenant_type,
  application_count,
  movein_count,
  application_to_movein_rate,
  updated_at
from aurora_gold.funnel_application_to_movein_periodized
where period_start >= current_date - interval 365 day
order by period_grain, period_start, municipality, nationality, tenant_type
```

```sql funnel_daily
select
  activity_date,
  municipality,
  nationality,
  tenant_type,
  application_count,
  movein_count,
  application_to_movein_rate,
  updated_at
from aurora_gold.funnel_application_to_movein_daily
where activity_date >= current_date - interval 180 day
order by activity_date, municipality, nationality, tenant_type
```

```sql funnel_latest_month
select
  period_start,
  sum(application_count) as application_count,
  sum(movein_count) as movein_count,
  cast(
    coalesce(sum(movein_count) / nullif(sum(application_count), 0), 0)
    as decimal(12, 4)
  ) as application_to_movein_rate
from aurora_gold.funnel_application_to_movein_periodized
where period_grain = 'monthly'
group by period_start
order by period_start desc
limit 1
```

```sql funnel_daily_total
select
  period_start,
  sum(application_count) as application_count,
  sum(movein_count) as movein_count,
  cast(
    coalesce(sum(movein_count) / nullif(sum(application_count), 0), 0)
    as decimal(12, 4)
  ) as application_to_movein_rate
from aurora_gold.funnel_application_to_movein_periodized
where period_grain = 'daily'
  and period_start >= current_date - interval 90 day
group by period_start
order by period_start
```

```sql funnel_weekly_total
select
  period_start,
  sum(application_count) as application_count,
  sum(movein_count) as movein_count,
  cast(
    coalesce(sum(movein_count) / nullif(sum(application_count), 0), 0)
    as decimal(12, 4)
  ) as application_to_movein_rate
from aurora_gold.funnel_application_to_movein_periodized
where period_grain = 'weekly'
  and period_start >= current_date - interval 365 day
group by period_start
order by period_start
```

```sql funnel_monthly_total
select
  period_start,
  sum(application_count) as application_count,
  sum(movein_count) as movein_count,
  cast(
    coalesce(sum(movein_count) / nullif(sum(application_count), 0), 0)
    as decimal(12, 4)
  ) as application_to_movein_rate
from aurora_gold.funnel_application_to_movein_periodized
where period_grain = 'monthly'
  and period_start >= current_date - interval 730 day
group by period_start
order by period_start
```

## Conversion Snapshot

<Grid cols={3} gapSize="md">
  <BigValue data={funnel_latest_month} title="Applications (Latest Month)" value="application_count" fmt="num0" />
  <BigValue data={funnel_latest_month} title="Move-ins (Latest Month)" value="movein_count" fmt="num0" />
  <BigValue data={funnel_latest_month} title="Application -> Move-in Rate" value="application_to_movein_rate" fmt="pct" />
</Grid>

## Period Controls

<Tabs background="true">
  <Tab label="Daily" id="daily">
    <LineChart data={funnel_daily_total} x=period_start y=application_to_movein_rate yFmt="pct" title="Daily Conversion Rate" />
    <BarChart data={funnel_daily_total} x=period_start y=application_count y2=movein_count title="Daily Applications vs Move-ins" />
  </Tab>

  <Tab label="Weekly" id="weekly">
    <LineChart data={funnel_weekly_total} x=period_start y=application_to_movein_rate yFmt="pct" title="Weekly Conversion Rate" />
    <BarChart data={funnel_weekly_total} x=period_start y=application_count y2=movein_count title="Weekly Applications vs Move-ins" />
  </Tab>

  <Tab label="Monthly" id="monthly">
    <LineChart data={funnel_monthly_total} x=period_start y=application_to_movein_rate yFmt="pct" title="Monthly Conversion Rate" />
    <BarChart data={funnel_monthly_total} x=period_start y=application_count y2=movein_count title="Monthly Applications vs Move-ins" />
  </Tab>
</Tabs>

## Municipality and Nationality Segmentation

```sql funnel_top_municipality
select
  municipality,
  sum(application_count) as application_count,
  sum(movein_count) as movein_count,
  cast(
    coalesce(sum(movein_count) / nullif(sum(application_count), 0), 0)
    as decimal(12, 4)
  ) as application_to_movein_rate
from aurora_gold.funnel_application_to_movein_daily
where activity_date >= current_date - interval 180 day
group by municipality
order by application_count desc
limit 25
```

```sql funnel_top_nationality
select
  nationality,
  sum(application_count) as application_count,
  sum(movein_count) as movein_count,
  cast(
    coalesce(sum(movein_count) / nullif(sum(application_count), 0), 0)
    as decimal(12, 4)
  ) as application_to_movein_rate
from aurora_gold.funnel_application_to_movein_daily
where activity_date >= current_date - interval 180 day
group by nationality
order by application_count desc
limit 25
```

<BarChart data={funnel_top_municipality} x=municipality y=application_to_movein_rate yFmt="pct" title="Top Municipalities by Conversion Rate" />

<BarChart data={funnel_top_nationality} x=nationality y=application_to_movein_rate yFmt="pct" title="Top Nationalities by Conversion Rate" />

## Corporate vs Individual Cohorts

```sql funnel_tenant_type_monthly
select
  period_start,
  tenant_type,
  sum(application_count) as application_count,
  sum(movein_count) as movein_count,
  cast(
    coalesce(sum(movein_count) / nullif(sum(application_count), 0), 0)
    as decimal(12, 4)
  ) as application_to_movein_rate
from aurora_gold.funnel_application_to_movein_periodized
where period_grain = 'monthly'
  and period_start >= current_date - interval 730 day
group by period_start, tenant_type
order by period_start, tenant_type
```

<LineChart
  data={funnel_tenant_type_monthly}
  x=period_start
  y=application_to_movein_rate
  series=tenant_type
  yFmt="pct"
  title="Monthly Conversion by tenant_type"
/>

<BarChart
  data={funnel_tenant_type_monthly}
  x=period_start
  y=application_count
  series=tenant_type
  type="stacked"
  title="Monthly Applications by tenant_type"
/>

## Detailed Funnel Tables

<DataTable data={funnel_periodized} />

<DataTable data={funnel_daily} />
