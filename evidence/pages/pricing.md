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
select
  period_start,
  tenant_type,
  sum(application_count) as application_count,
  sum(movein_count) as movein_count,
  cast(
    coalesce(100.0 * sum(movein_count) / nullif(sum(application_count), 0), 0)
    as decimal(12, 2)
  ) as conversion_rate_pct
from aurora_gold.funnel_application_to_movein_periodized
where period_grain = 'monthly'
  and period_start >= current_date - interval 730 day
group by period_start, tenant_type
order by period_start, tenant_type
```

```sql conversion_trend_monthly_total
select
  period_start,
  sum(application_count) as application_count,
  sum(movein_count) as movein_count,
  cast(
    coalesce(100.0 * sum(movein_count) / nullif(sum(application_count), 0), 0)
    as decimal(12, 2)
  ) as conversion_rate_pct
from aurora_gold.funnel_application_to_movein_periodized
where period_grain = 'monthly'
  and period_start >= current_date - interval 730 day
group by period_start
order by period_start
```

```sql segment_pressure_ranking
select
  concat(segment_type, ': ', segment_value) as segment_label,
  segment_type,
  segment_value,
  sum(application_count) as application_count,
  sum(movein_count) as movein_count,
  cast(
    coalesce(100.0 * sum(movein_count) / nullif(sum(application_count), 0), 0)
    as decimal(12, 2)
  ) as conversion_rate_pct
from aurora_gold.funnel_application_to_movein_segment_share
where period_grain = 'monthly'
  and period_start >= current_date - interval 365 day
  and segment_type in ('municipality', 'nationality')
  and coalesce(segment_value, '') <> ''
group by segment_type, segment_value
having sum(application_count) >= 10
order by conversion_rate_pct asc, application_count desc
limit 30
```

```sql segment_share_detail
select
  period_grain,
  period_start,
  tenant_type,
  segment_type,
  segment_value,
  application_count,
  movein_count,
  round(application_share * 100, 2) as application_share_pct,
  round(movein_share * 100, 2) as movein_share_pct,
  round(application_to_movein_rate * 100, 2) as conversion_rate_pct,
  segment_rank,
  updated_at
from aurora_gold.funnel_application_to_movein_segment_share
where period_grain in ('weekly', 'monthly')
  and period_start >= current_date - interval 365 day
order by period_grain, period_start desc, segment_type, tenant_type, segment_rank
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
Freshness: KPI block follows `funnel_application_to_movein_segment_share.updated_at` at source refresh.
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
Freshness: municipality parity updates with the newest segment-share `updated_at` records.
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
Freshness: nationality parity updates with the newest segment-share `updated_at` records.
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
Freshness: trend sections inherit periodized funnel freshness via source `updated_at`.
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
Freshness: rankings reflect the latest monthly segment-share refresh.
</Note>

## Segment Share Detail

<DataTable data={segment_share_detail} downloadable={true} />

<Note>
Time basis: weekly and monthly `period_start` rows from segment-share contract output.
Freshness: row-level recency is visible in `segment_share_detail.updated_at`.
</Note>
