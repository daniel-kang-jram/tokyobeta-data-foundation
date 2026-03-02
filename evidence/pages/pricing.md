# Pricing and Segment Parity (Gold)

## Storyline

This page answers: **which municipality and nationality segments are driving
pricing pressure in the application -> move-in funnel, and where should operators
focus next?**

```sql segment_share_kpis
with latest_month as (
  select max(period_start) as period_start
  from aurora_gold.funnel_application_to_movein_segment_share
  where period_grain = 'monthly'
),
segment_rollup as (
  select
    segment_type,
    segment_value,
    sum(application_count) as application_count,
    sum(movein_count) as movein_count,
    cast(
      coalesce(100.0 * sum(movein_count) / nullif(sum(application_count), 0), 0)
      as decimal(12, 2)
    ) as conversion_rate_pct
  from aurora_gold.funnel_application_to_movein_segment_share s
  join latest_month m
    on s.period_start = m.period_start
  where s.period_grain = 'monthly'
    and s.segment_type in ('municipality', 'nationality')
  group by segment_type, segment_value
),
overall as (
  select
    sum(application_count) as total_applications,
    sum(movein_count) as total_moveins,
    cast(
      coalesce(100.0 * sum(movein_count) / nullif(sum(application_count), 0), 0)
      as decimal(12, 2)
    ) as overall_conversion_rate_pct
  from segment_rollup
),
weakest as (
  select
    concat(segment_type, ': ', segment_value) as weakest_segment,
    conversion_rate_pct as weakest_conversion_rate_pct
  from segment_rollup
  order by conversion_rate_pct asc, application_count desc
  limit 1
),
largest as (
  select
    concat(segment_type, ': ', segment_value) as largest_segment,
    application_count as largest_segment_applications
  from segment_rollup
  order by application_count desc
  limit 1
)
select
  o.total_applications,
  o.total_moveins,
  o.overall_conversion_rate_pct,
  w.weakest_segment,
  w.weakest_conversion_rate_pct,
  l.largest_segment,
  l.largest_segment_applications
from overall o
cross join weakest w
cross join largest l
```

```sql municipality_pie
with latest_month as (
  select max(period_start) as period_start
  from aurora_gold.funnel_application_to_movein_segment_share
  where period_grain = 'monthly'
),
base as (
  select
    segment_value,
    sum(application_count) as application_count,
    sum(movein_count) as movein_count
  from aurora_gold.funnel_application_to_movein_segment_share s
  join latest_month m
    on s.period_start = m.period_start
  where s.period_grain = 'monthly'
    and s.segment_type = 'municipality'
    and coalesce(segment_value, '') <> ''
  group by segment_value
),
totals as (
  select
    sum(application_count) as total_applications,
    sum(movein_count) as total_moveins
  from base
)
select
  b.segment_value,
  b.application_count,
  b.movein_count,
  cast(
    coalesce(100.0 * b.application_count / nullif(t.total_applications, 0), 0)
    as decimal(12, 2)
  ) as application_share_pct,
  cast(
    coalesce(100.0 * b.movein_count / nullif(t.total_moveins, 0), 0)
    as decimal(12, 2)
  ) as movein_share_pct,
  cast(
    coalesce(100.0 * b.movein_count / nullif(b.application_count, 0), 0)
    as decimal(12, 2)
  ) as conversion_rate_pct
from base b
cross join totals t
order by b.application_count desc, b.segment_value
limit 12
```

```sql nationality_pie
with latest_month as (
  select max(period_start) as period_start
  from aurora_gold.funnel_application_to_movein_segment_share
  where period_grain = 'monthly'
),
base as (
  select
    segment_value,
    sum(application_count) as application_count,
    sum(movein_count) as movein_count
  from aurora_gold.funnel_application_to_movein_segment_share s
  join latest_month m
    on s.period_start = m.period_start
  where s.period_grain = 'monthly'
    and s.segment_type = 'nationality'
    and coalesce(segment_value, '') <> ''
  group by segment_value
),
totals as (
  select
    sum(application_count) as total_applications,
    sum(movein_count) as total_moveins
  from base
)
select
  b.segment_value,
  b.application_count,
  b.movein_count,
  cast(
    coalesce(100.0 * b.application_count / nullif(t.total_applications, 0), 0)
    as decimal(12, 2)
  ) as application_share_pct,
  cast(
    coalesce(100.0 * b.movein_count / nullif(t.total_moveins, 0), 0)
    as decimal(12, 2)
  ) as movein_share_pct,
  cast(
    coalesce(100.0 * b.movein_count / nullif(b.application_count, 0), 0)
    as decimal(12, 2)
  ) as conversion_rate_pct
from base b
cross join totals t
order by b.application_count desc, b.segment_value
limit 12
```

```sql conversion_trend_monthly
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
    coalesce(100.0 * sum(p.movein_count) / nullif(sum(p.application_count), 0), 0)
    as decimal(12, 2)
  ) as conversion_rate_pct
from aurora_gold.funnel_application_to_movein_periodized p
cross join data_max m
where p.period_grain = 'monthly'
  and p.period_start >= m.max_period_start - interval 730 day
group by p.period_start, p.tenant_type
order by p.period_start, p.tenant_type
```

```sql conversion_trend_monthly_total
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
    coalesce(100.0 * sum(p.movein_count) / nullif(sum(p.application_count), 0), 0)
    as decimal(12, 2)
  ) as conversion_rate_pct
from aurora_gold.funnel_application_to_movein_periodized p
cross join data_max m
where p.period_grain = 'monthly'
  and p.period_start >= m.max_period_start - interval 730 day
group by p.period_start
order by p.period_start
```

```sql segment_pressure_ranking
with data_max as (
  select max(period_start) as max_period_start
  from aurora_gold.funnel_application_to_movein_segment_share
  where period_grain = 'monthly'
)
select
  concat(s.segment_type, ': ', s.segment_value) as segment_label,
  s.segment_type,
  s.segment_value,
  sum(s.application_count) as application_count,
  sum(s.movein_count) as movein_count,
  cast(
    coalesce(100.0 * sum(s.movein_count) / nullif(sum(s.application_count), 0), 0)
    as decimal(12, 2)
  ) as conversion_rate_pct
from aurora_gold.funnel_application_to_movein_segment_share s
cross join data_max m
where s.period_grain = 'monthly'
  and s.period_start >= m.max_period_start - interval 365 day
  and s.segment_type in ('municipality', 'nationality')
  and coalesce(s.segment_value, '') <> ''
group by s.segment_type, s.segment_value
having sum(s.application_count) >= 10
order by conversion_rate_pct asc, application_count desc
limit 30
```

```sql segment_share_detail
with data_max as (
  select
    max(case when period_grain = 'weekly' then period_start end) as max_weekly_period_start,
    max(case when period_grain = 'monthly' then period_start end) as max_monthly_period_start
  from aurora_gold.funnel_application_to_movein_segment_share
)
select
  s.period_grain,
  s.period_start,
  s.tenant_type,
  s.segment_type,
  s.segment_value,
  s.application_count,
  s.movein_count,
  round(s.application_share * 100, 2) as application_share_pct,
  round(s.movein_share * 100, 2) as movein_share_pct,
  round(s.application_to_movein_rate * 100, 2) as conversion_rate_pct,
  s.segment_rank,
  s.updated_at
from aurora_gold.funnel_application_to_movein_segment_share s
cross join data_max m
where (s.period_grain = 'weekly' and s.period_start >= m.max_weekly_period_start - interval 365 day)
   or (s.period_grain = 'monthly' and s.period_start >= m.max_monthly_period_start - interval 365 day)
order by s.period_grain, s.period_start desc, s.segment_type, s.tenant_type, s.segment_rank
```

```sql pricing_segment_monthly_coverage
select
  min(period_start) as coverage_from,
  max(period_start) as coverage_to,
  max(updated_at) as freshness_updated_at
from aurora_gold.funnel_application_to_movein_segment_share
where period_grain = 'monthly'
```

```sql pricing_segment_weekly_coverage
select
  min(period_start) as coverage_from,
  max(period_start) as coverage_to,
  max(updated_at) as freshness_updated_at
from aurora_gold.funnel_application_to_movein_segment_share
where period_grain = 'weekly'
```

```sql pricing_monthly_trend_coverage
select
  min(period_start) as coverage_from,
  max(period_start) as coverage_to,
  max(updated_at) as freshness_updated_at
from aurora_gold.funnel_application_to_movein_periodized
where period_grain = 'monthly'
```

<Grid cols={3} gapSize="md">
  <BigValue
    data={segment_share_kpis}
    title="Applications (Latest Month)"
    value="total_applications"
    fmt="num0"
  />
  <BigValue
    data={segment_share_kpis}
    title="Move-ins (Latest Month)"
    value="total_moveins"
    fmt="num0"
  />
  <BigValue
    data={segment_share_kpis}
    title="Overall Conversion Rate (%)"
    value="overall_conversion_rate_pct"
    fmt="num2"
  />
</Grid>

<ul>
  <li>
    Weakest segment: <strong>{segment_share_kpis[0].weakest_segment}</strong>
    ({segment_share_kpis[0].weakest_conversion_rate_pct}%).
  </li>
  <li>
    Largest application segment: <strong>{segment_share_kpis[0].largest_segment}</strong>
    ({segment_share_kpis[0].largest_segment_applications} applications).
  </li>
</ul>

<Note>
Time basis: latest monthly `period_start` from `funnel_application_to_movein_segment_share`.
Coverage: {pricing_segment_monthly_coverage[0].coverage_from} to {pricing_segment_monthly_coverage[0].coverage_to}.
Freshness: {pricing_segment_monthly_coverage[0].freshness_updated_at}.
</Note>

## Municipality Segment Parity (Applications vs Move-ins)

<ECharts
  data={municipality_pie}
  config={{
    title: [
      { text: 'Application Share %', left: '25%', top: 0, textAlign: 'center' },
      { text: 'Move-in Share %', left: '75%', top: 0, textAlign: 'center' }
    ],
    tooltip: { trigger: 'item' },
    legend: { type: 'scroll', bottom: 0 },
    series: [
      {
        type: 'pie',
        radius: '52%',
        center: ['25%', '55%'],
        data: municipality_pie.map((d) => ({ name: d.segment_value, value: d.application_share_pct }))
      },
      {
        type: 'pie',
        radius: '52%',
        center: ['75%', '55%'],
        data: municipality_pie.map((d) => ({ name: d.segment_value, value: d.movein_share_pct }))
      }
    ]
  }}
/>

<DataTable data={municipality_pie} downloadable={true} />

<Note>
Time basis: latest monthly segment shares for `segment_type = municipality`.
Coverage: {pricing_segment_monthly_coverage[0].coverage_from} to {pricing_segment_monthly_coverage[0].coverage_to}.
Freshness: {pricing_segment_monthly_coverage[0].freshness_updated_at}.
</Note>

## Nationality Segment Parity (Applications vs Move-ins)

<ECharts
  data={nationality_pie}
  config={{
    title: [
      { text: 'Application Share %', left: '25%', top: 0, textAlign: 'center' },
      { text: 'Move-in Share %', left: '75%', top: 0, textAlign: 'center' }
    ],
    tooltip: { trigger: 'item' },
    legend: { type: 'scroll', bottom: 0 },
    series: [
      {
        type: 'pie',
        radius: '52%',
        center: ['25%', '55%'],
        data: nationality_pie.map((d) => ({ name: d.segment_value, value: d.application_share_pct }))
      },
      {
        type: 'pie',
        radius: '52%',
        center: ['75%', '55%'],
        data: nationality_pie.map((d) => ({ name: d.segment_value, value: d.movein_share_pct }))
      }
    ]
  }}
/>

<DataTable data={nationality_pie} downloadable={true} />

<Note>
Time basis: latest monthly segment shares for `segment_type = nationality`.
Coverage: {pricing_segment_monthly_coverage[0].coverage_from} to {pricing_segment_monthly_coverage[0].coverage_to}.
Freshness: {pricing_segment_monthly_coverage[0].freshness_updated_at}.
</Note>

## Monthly Conversion Trend

<LineChart
  data={conversion_trend_monthly_total}
  x=period_start
  y=conversion_rate_pct
  title="Portfolio Conversion Rate (Monthly)"
  yFmt="num2"
/>

<BarChart
  data={conversion_trend_monthly}
  x=period_start
  y=application_count
  series=tenant_type
  type="stacked"
  title="Monthly Applications by tenant_type"
/>

<LineChart
  data={conversion_trend_monthly}
  x=period_start
  y=conversion_rate_pct
  series=tenant_type
  title="Monthly Conversion Rate by tenant_type"
  yFmt="num2"
/>

<Note>
Time basis: monthly `period_start` rows from `funnel_application_to_movein_periodized`.
Coverage: {pricing_monthly_trend_coverage[0].coverage_from} to {pricing_monthly_trend_coverage[0].coverage_to}.
Freshness: {pricing_monthly_trend_coverage[0].freshness_updated_at}.
</Note>

## Segment Pressure Ranking

<BarChart
  data={segment_pressure_ranking}
  x=segment_label
  y=conversion_rate_pct
  swapXY={true}
  chartAreaHeight={900}
  title="Lowest Conversion Segments (12-Month Window)"
/>

<DataTable data={segment_pressure_ranking} downloadable={true} />

<Note>
Time basis: rolling 12-month monthly window from `funnel_application_to_movein_segment_share`.
Coverage: {pricing_segment_monthly_coverage[0].coverage_from} to {pricing_segment_monthly_coverage[0].coverage_to}.
Freshness: {pricing_segment_monthly_coverage[0].freshness_updated_at}.
</Note>

## Segment Share Detail

<DataTable data={segment_share_detail} downloadable={true} />

<Note>
Time basis: weekly and monthly `period_start` rows from segment-share contract output.
Coverage: Weekly {pricing_segment_weekly_coverage[0].coverage_from} to {pricing_segment_weekly_coverage[0].coverage_to}; Monthly {pricing_segment_monthly_coverage[0].coverage_from} to {pricing_segment_monthly_coverage[0].coverage_to}.
Freshness: Weekly {pricing_segment_weekly_coverage[0].freshness_updated_at}; Monthly {pricing_segment_monthly_coverage[0].freshness_updated_at}.
</Note>
