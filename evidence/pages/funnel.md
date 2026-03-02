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
with data_max as (
  select max(period_start) as max_period_start
  from aurora_gold.funnel_application_to_movein_periodized
  where period_grain = 'daily'
)
select
  p.period_start,
  sum(p.application_count) as application_count,
  sum(p.movein_count) as movein_count,
  cast(
    coalesce(sum(p.movein_count) / nullif(sum(p.application_count), 0), 0)
    as decimal(12, 4)
  ) as application_to_movein_rate
from aurora_gold.funnel_application_to_movein_periodized p
cross join data_max m
where p.period_grain = 'daily'
  and p.period_start >= m.max_period_start - interval 90 day
group by p.period_start
order by p.period_start
```

```sql funnel_weekly_total
with data_max as (
  select max(period_start) as max_period_start
  from aurora_gold.funnel_application_to_movein_periodized
  where period_grain = 'weekly'
)
select
  p.period_start,
  sum(p.application_count) as application_count,
  sum(p.movein_count) as movein_count,
  cast(
    coalesce(sum(p.movein_count) / nullif(sum(p.application_count), 0), 0)
    as decimal(12, 4)
  ) as application_to_movein_rate
from aurora_gold.funnel_application_to_movein_periodized p
cross join data_max m
where p.period_grain = 'weekly'
  and p.period_start >= m.max_period_start - interval 365 day
group by p.period_start
order by p.period_start
```

```sql funnel_monthly_total
with data_max as (
  select max(period_start) as max_period_start
  from aurora_gold.funnel_application_to_movein_periodized
  where period_grain = 'monthly'
)
select
  p.period_start,
  sum(p.application_count) as application_count,
  sum(p.movein_count) as movein_count,
  cast(
    coalesce(sum(p.movein_count) / nullif(sum(p.application_count), 0), 0)
    as decimal(12, 4)
  ) as application_to_movein_rate
from aurora_gold.funnel_application_to_movein_periodized p
cross join data_max m
where p.period_grain = 'monthly'
  and p.period_start >= m.max_period_start - interval 730 day
group by p.period_start
order by p.period_start
```

```sql funnel_daily_coverage
select
  min(activity_date) as coverage_from,
  max(activity_date) as coverage_to,
  max(updated_at) as freshness_updated_at
from aurora_gold.funnel_application_to_movein_daily
```

```sql funnel_daily_period_coverage
select
  min(period_start) as coverage_from,
  max(period_start) as coverage_to,
  max(updated_at) as freshness_updated_at
from aurora_gold.funnel_application_to_movein_periodized
where period_grain = 'daily'
```

```sql funnel_weekly_period_coverage
select
  min(period_start) as coverage_from,
  max(period_start) as coverage_to,
  max(updated_at) as freshness_updated_at
from aurora_gold.funnel_application_to_movein_periodized
where period_grain = 'weekly'
```

```sql funnel_monthly_period_coverage
select
  min(period_start) as coverage_from,
  max(period_start) as coverage_to,
  max(updated_at) as freshness_updated_at
from aurora_gold.funnel_application_to_movein_periodized
where period_grain = 'monthly'
```

## Conversion Snapshot

<Grid cols={3} gapSize="md">
  <BigValue data={funnel_latest_month} title="Applications (Latest Month)" value="application_count" fmt="num0" />
  <BigValue data={funnel_latest_month} title="Move-ins (Latest Month)" value="movein_count" fmt="num0" />
  <BigValue data={funnel_latest_month} title="Overall Conversion Rate (%)" value="application_to_movein_rate" fmt="pct" />
</Grid>

<Note>
Time basis: latest monthly `period_start` from `funnel_application_to_movein_periodized`.
Coverage: {funnel_monthly_period_coverage[0].coverage_from} to {funnel_monthly_period_coverage[0].coverage_to}.
Freshness: {funnel_monthly_period_coverage[0].freshness_updated_at}.
</Note>

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

<Note>
Time basis: period controls switch `period_grain` and `period_start` in `funnel_application_to_movein_periodized`.
Coverage: Daily {funnel_daily_period_coverage[0].coverage_from} to {funnel_daily_period_coverage[0].coverage_to}; Weekly {funnel_weekly_period_coverage[0].coverage_from} to {funnel_weekly_period_coverage[0].coverage_to}; Monthly {funnel_monthly_period_coverage[0].coverage_from} to {funnel_monthly_period_coverage[0].coverage_to}.
Freshness: Daily {funnel_daily_period_coverage[0].freshness_updated_at}; Weekly {funnel_weekly_period_coverage[0].freshness_updated_at}; Monthly {funnel_monthly_period_coverage[0].freshness_updated_at}.
</Note>

```sql funnel_top_municipality
with data_max as (
  select max(activity_date) as max_activity_date
  from aurora_gold.funnel_application_to_movein_daily
)
select
  d.municipality,
  sum(d.application_count) as application_count,
  sum(d.movein_count) as movein_count,
  cast(
    coalesce(sum(d.movein_count) / nullif(sum(d.application_count), 0), 0)
    as decimal(12, 4)
  ) as application_to_movein_rate
from aurora_gold.funnel_application_to_movein_daily d
cross join data_max m
where d.activity_date >= m.max_activity_date - interval 180 day
group by d.municipality
order by application_count desc
limit 25
```

```sql funnel_top_nationality
with data_max as (
  select max(activity_date) as max_activity_date
  from aurora_gold.funnel_application_to_movein_daily
)
select
  d.nationality,
  sum(d.application_count) as application_count,
  sum(d.movein_count) as movein_count,
  cast(
    coalesce(sum(d.movein_count) / nullif(sum(d.application_count), 0), 0)
    as decimal(12, 4)
  ) as application_to_movein_rate
from aurora_gold.funnel_application_to_movein_daily d
cross join data_max m
where d.activity_date >= m.max_activity_date - interval 180 day
group by d.nationality
order by application_count desc
limit 25
```

## Municipality Segment Parity (Applications vs Move-ins)

<BarChart data={funnel_top_municipality} x=municipality y=application_to_movein_rate yFmt="pct" title="Top Municipalities by Conversion Rate" />

<Note>
Time basis: municipality parity uses `funnel_application_to_movein_daily.activity_date`.
Coverage: {funnel_daily_coverage[0].coverage_from} to {funnel_daily_coverage[0].coverage_to}.
Freshness: {funnel_daily_coverage[0].freshness_updated_at}.
</Note>

## Nationality Segment Parity (Applications vs Move-ins)

<BarChart data={funnel_top_nationality} x=nationality y=application_to_movein_rate yFmt="pct" title="Top Nationalities by Conversion Rate" />

<Note>
Time basis: nationality parity uses `funnel_application_to_movein_daily.activity_date`.
Coverage: {funnel_daily_coverage[0].coverage_from} to {funnel_daily_coverage[0].coverage_to}.
Freshness: {funnel_daily_coverage[0].freshness_updated_at}.
</Note>

```sql funnel_tenant_type_monthly
with data_max as (
  select max(period_start) as max_period_start
  from aurora_gold.funnel_application_to_movein_periodized
  where period_grain = 'monthly'
)
select
  p.period_start,
  p.tenant_type,
  sum(p.application_count) as application_count,
  sum(p.movein_count) as movein_count,
  cast(
    coalesce(sum(p.movein_count) / nullif(sum(p.application_count), 0), 0)
    as decimal(12, 4)
  ) as application_to_movein_rate
from aurora_gold.funnel_application_to_movein_periodized p
cross join data_max m
where p.period_grain = 'monthly'
  and p.period_start >= m.max_period_start - interval 730 day
group by p.period_start, p.tenant_type
order by p.period_start, p.tenant_type
```

## Monthly Conversion Trend

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

<Note>
Time basis: cohort trends are monthly `period_start` by `tenant_type`.
Coverage: {funnel_monthly_period_coverage[0].coverage_from} to {funnel_monthly_period_coverage[0].coverage_to}.
Freshness: {funnel_monthly_period_coverage[0].freshness_updated_at}.
</Note>

```sql moveout_movein_monthly_parity
with moveout_monthly as (
  select
    cast(date_trunc('month', moveout_date) as date) as period_start,
    count(*) as moveout_count
  from aurora_gold.moveout_analysis_recent
  group by cast(date_trunc('month', moveout_date) as date)
),
movein_monthly as (
  select
    cast(date_trunc('month', contract_start_date) as date) as period_start,
    count(*) as movein_count
  from aurora_gold.movein_analysis_recent
  group by cast(date_trunc('month', contract_start_date) as date)
),
combined_periods as (
  select period_start from moveout_monthly
  union
  select period_start from movein_monthly
),
parity as (
  select
    p.period_start,
    coalesce(o.moveout_count, 0) as moveout_count,
    coalesce(i.movein_count, 0) as movein_count
  from combined_periods p
  left join moveout_monthly o on p.period_start = o.period_start
  left join movein_monthly i on p.period_start = i.period_start
),
data_max as (
  select max(period_start) as max_period_start
  from parity
)
select
  parity.period_start,
  parity.moveout_count,
  parity.movein_count,
  cast(
    coalesce(100.0 * parity.movein_count / nullif(parity.moveout_count, 0), 0)
    as decimal(12, 2)
  ) as moveout_to_movein_rate_pct
from parity
cross join data_max
where parity.period_start >= data_max.max_period_start - interval 12 month
order by parity.period_start
```

```sql moveout_movein_parity_coverage
with moveout_monthly as (
  select cast(date_trunc('month', moveout_date) as date) as period_start
  from aurora_gold.moveout_analysis_recent
),
movein_monthly as (
  select cast(date_trunc('month', contract_start_date) as date) as period_start
  from aurora_gold.movein_analysis_recent
),
combined_periods as (
  select period_start from moveout_monthly
  union
  select period_start from movein_monthly
),
data_max as (
  select max(period_start) as max_period_start
  from combined_periods
)
select
  min(period_start) as coverage_from,
  max(period_start) as coverage_to,
  max(data_max.max_period_start) as freshness_period
from combined_periods
cross join data_max
where period_start >= data_max.max_period_start - interval 12 month
```

## Moveout -> Move-in Snapshot Parity

<BarChart
  data={moveout_movein_monthly_parity}
  x=period_start
  y=moveout_count
  y2=movein_count
  title="Monthly Moveout vs Move-in Counts"
/>

<LineChart
  data={moveout_movein_monthly_parity}
  x=period_start
  y=moveout_to_movein_rate_pct
  yFmt="num2"
  title="Moveout -> Move-in Parity Rate (%)"
/>

<DataTable data={moveout_movein_monthly_parity} downloadable={true} />

<Note>
Time basis: monthly period snapshots using `moveout_analysis_recent.moveout_date` and `movein_analysis_recent.contract_start_date`.
Coverage: {moveout_movein_parity_coverage[0].coverage_from} to {moveout_movein_parity_coverage[0].coverage_to}.
Freshness: latest parity period is {moveout_movein_parity_coverage[0].freshness_period}.
</Note>

## Detailed Funnel Tables

<DataTable data={funnel_periodized} downloadable={true} />

<DataTable data={funnel_daily} downloadable={true} />
