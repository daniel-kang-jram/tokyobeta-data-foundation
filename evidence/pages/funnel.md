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

```sql funnel_daily_period_coverage
select
  substr(cast(min(period_start) as varchar), 1, 10) as coverage_from,
  substr(cast(max(period_start) as varchar), 1, 10) as coverage_to,
  substr(cast(max(updated_at) as varchar), 1, 10) as freshness_updated_at
from aurora_gold.funnel_application_to_movein_periodized
where period_grain = 'daily'
```

```sql funnel_weekly_period_coverage
select
  substr(cast(min(period_start) as varchar), 1, 10) as coverage_from,
  substr(cast(max(period_start) as varchar), 1, 10) as coverage_to,
  substr(cast(max(updated_at) as varchar), 1, 10) as freshness_updated_at
from aurora_gold.funnel_application_to_movein_periodized
where period_grain = 'weekly'
```

```sql funnel_monthly_period_coverage
select
  substr(cast(min(period_start) as varchar), 1, 10) as coverage_from,
  substr(cast(max(period_start) as varchar), 1, 10) as coverage_to,
  substr(cast(max(updated_at) as varchar), 1, 10) as freshness_updated_at
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
Time basis: latest monthly `period_start` snapshot.
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
Time basis: tabs switch `period_grain` and `period_start`.
Coverage: Daily {funnel_daily_period_coverage[0].coverage_from} to {funnel_daily_period_coverage[0].coverage_to}; Weekly {funnel_weekly_period_coverage[0].coverage_from} to {funnel_weekly_period_coverage[0].coverage_to}; Monthly {funnel_monthly_period_coverage[0].coverage_from} to {funnel_monthly_period_coverage[0].coverage_to}.
Freshness: Daily {funnel_daily_period_coverage[0].freshness_updated_at}; Weekly {funnel_weekly_period_coverage[0].freshness_updated_at}; Monthly {funnel_monthly_period_coverage[0].freshness_updated_at}.
</Note>

```sql replacement_flow_sankey
with moveout_seg as (
  select
    coalesce(nullif(trim(municipality), ''), 'unknown') as municipality,
    coalesce(nullif(trim(nationality), ''), 'unknown') as nationality,
    case
      when tenant_type in ('individual', 'corporate') then tenant_type
      else 'unknown'
    end as tenant_type,
    coalesce(nullif(trim(rent_range), ''), 'unknown') as rent_band,
    count(*) as moveout_count
  from aurora_gold.moveout_analysis_recent
  where moveout_date >= current_date - interval 180 day
  group by municipality, nationality, tenant_type, rent_band
),
movein_seg as (
  select
    coalesce(nullif(trim(municipality), ''), 'unknown') as municipality,
    coalesce(nullif(trim(nationality), ''), 'unknown') as nationality,
    case
      when tenant_type in ('individual', 'corporate') then tenant_type
      else 'unknown'
    end as tenant_type,
    coalesce(nullif(trim(rent_range), ''), 'unknown') as rent_band,
    count(*) as movein_count
  from aurora_gold.movein_analysis_recent
  where contract_start_date >= current_date - interval 180 day
  group by municipality, nationality, tenant_type, rent_band
),
seg as (
  select
    coalesce(o.municipality, i.municipality) as municipality,
    coalesce(o.nationality, i.nationality) as nationality,
    coalesce(o.tenant_type, i.tenant_type) as tenant_type,
    coalesce(o.rent_band, i.rent_band) as rent_band,
    coalesce(o.moveout_count, 0) as moveout_count,
    coalesce(i.movein_count, 0) as movein_count
  from moveout_seg o
  full join movein_seg i
    on o.municipality = i.municipality
   and o.nationality = i.nationality
   and o.tenant_type = i.tenant_type
   and o.rent_band = i.rent_band
),
focus as (
  select
    municipality,
    nationality,
    tenant_type,
    rent_band,
    municipality || ' | ' || nationality || ' | ' || tenant_type || ' | ' || rent_band as segment_key,
    moveout_count,
    movein_count
  from seg
  where moveout_count > 0 or movein_count > 0
  order by abs(moveout_count - movein_count) desc, moveout_count desc, movein_count desc
  limit 18
),
links as (
  select
    'Move-out planned' as source,
    segment_key as target,
    moveout_count as value,
    'out' as link_type
  from focus

  union all

  select
    segment_key as source,
    'Move-in planned' as target,
    movein_count as value,
    'in' as link_type
  from focus
)
select
  source,
  target,
  value,
  link_type
from links
where value > 0
order by value desc
```

```sql replacement_flow_summary
with moveout_seg as (
  select
    coalesce(nullif(trim(municipality), ''), 'unknown') as municipality,
    coalesce(nullif(trim(nationality), ''), 'unknown') as nationality,
    case
      when tenant_type in ('individual', 'corporate') then tenant_type
      else 'unknown'
    end as tenant_type,
    coalesce(nullif(trim(rent_range), ''), 'unknown') as rent_band,
    count(*) as moveout_count
  from aurora_gold.moveout_analysis_recent
  where moveout_date >= current_date - interval 180 day
  group by municipality, nationality, tenant_type, rent_band
),
movein_seg as (
  select
    coalesce(nullif(trim(municipality), ''), 'unknown') as municipality,
    coalesce(nullif(trim(nationality), ''), 'unknown') as nationality,
    case
      when tenant_type in ('individual', 'corporate') then tenant_type
      else 'unknown'
    end as tenant_type,
    coalesce(nullif(trim(rent_range), ''), 'unknown') as rent_band,
    count(*) as movein_count
  from aurora_gold.movein_analysis_recent
  where contract_start_date >= current_date - interval 180 day
  group by municipality, nationality, tenant_type, rent_band
),
seg as (
  select
    coalesce(o.municipality, i.municipality) as municipality,
    coalesce(o.nationality, i.nationality) as nationality,
    coalesce(o.tenant_type, i.tenant_type) as tenant_type,
    coalesce(o.rent_band, i.rent_band) as rent_band,
    coalesce(o.moveout_count, 0) as moveout_count,
    coalesce(i.movein_count, 0) as movein_count
  from moveout_seg o
  full join movein_seg i
    on o.municipality = i.municipality
   and o.nationality = i.nationality
   and o.tenant_type = i.tenant_type
   and o.rent_band = i.rent_band
),
focus as (
  select *
  from seg
  where moveout_count > 0 or movein_count > 0
)
select
  sum(moveout_count) as focus_moveout,
  sum(movein_count) as focus_movein,
  sum(movein_count) - sum(moveout_count) as focus_net,
  cast(coalesce(sum(movein_count) / nullif(sum(moveout_count), 0), 0) as decimal(12, 3)) as focus_replacement_ratio
from focus
```

```sql replacement_flow_coverage
with combined as (
  select moveout_date as event_date, updated_at
  from aurora_gold.moveout_analysis_recent
  where moveout_date >= current_date - interval 180 day

  union all

  select contract_start_date as event_date, updated_at
  from aurora_gold.movein_analysis_recent
  where contract_start_date >= current_date - interval 180 day
)
select
  substr(cast(min(event_date) as varchar), 1, 10) as coverage_from,
  substr(cast(max(event_date) as varchar), 1, 10) as coverage_to,
  substr(cast(max(updated_at) as varchar), 1, 10) as freshness_updated_at
from combined
```

## Killer Chart: Replacement Failure Flow

<Grid cols={4} gapSize="md">
  <BigValue data={replacement_flow_summary} title="Planned Move-outs (180d)" value="focus_moveout" fmt="num0" />
  <BigValue data={replacement_flow_summary} title="Planned Move-ins (180d)" value="focus_movein" fmt="num0" />
  <BigValue data={replacement_flow_summary} title="Net Replacement (180d)" value="focus_net" fmt="num0" />
  <BigValue data={replacement_flow_summary} title="Replacement Ratio" value="focus_replacement_ratio" fmt="num2" />
</Grid>

<ECharts
  data={replacement_flow_sankey}
  config={{
    tooltip: { trigger: 'item' },
    series: [
      {
        type: 'sankey',
        nodeAlign: 'justify',
        lineStyle: { curveness: 0.5, opacity: 0.55 },
        emphasis: { focus: 'adjacency' },
        data: [...new Set(replacement_flow_sankey.flatMap((d) => [d.source, d.target]))].map((name) => ({ name })),
        links: replacement_flow_sankey.map((d) => ({
          source: d.source,
          target: d.target,
          value: d.value,
          lineStyle: {
            color:
              d.link_type === 'out'
                ? '#dc2626'
                : d.link_type === 'in'
                  ? '#16a34a'
                  : '#64748b'
          }
        }))
      }
    ]
  }}
/>

<DataTable data={replacement_flow_sankey} downloadable={true} />

<Note>
Time basis: latest 180-day replacement snapshot by municipality, nationality, tenant_type, and rent_band.
Coverage: {replacement_flow_coverage[0].coverage_from} to {replacement_flow_coverage[0].coverage_to}.
Freshness: {replacement_flow_coverage[0].freshness_updated_at}.
Move-out planned flow (red): segment links track planned move-out volume.
Move-in planned flow (green): segment links track planned move-in replacements.
</Note>

## Detailed Funnel Tables

<DataTable data={funnel_periodized} downloadable={true} />

<DataTable data={funnel_daily} downloadable={true} />
