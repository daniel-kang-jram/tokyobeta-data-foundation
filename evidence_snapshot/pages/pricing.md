# Pricing and Portfolio Risk

## Storyline

This page answers: **Which segments are most exposed to vacancy risk, and what
pricing/retention actions are justified by the snapshot?**

Because rent-band volumes are highly imbalanced, this page is ratio-first
(replacement rate, outflow share, and churn pressure), not raw net count-first.

```sql rent_band_ratio_profile
with base as (
  select
    rent_band,
    movein_count,
    moveout_count,
    net_change,
    case rent_band
      when '<50k' then 1
      when '50-59k' then 2
      when '60-69k' then 3
      when '70-79k' then 4
      when '80k+' then 5
      else 99
    end as band_order
  from snapshot_csv.rent_band_inout_balance
),
totals as (
  select
    sum(movein_count) as total_moveins,
    sum(moveout_count) as total_moveouts
  from base
)
select
  b.rent_band,
  b.band_order,
  b.movein_count,
  b.moveout_count,
  b.net_change,
  round(100.0 * b.movein_count / nullif(b.moveout_count, 0), 2) as replacement_rate_percent,
  round(100.0 * (b.moveout_count - b.movein_count) / nullif(b.moveout_count, 0), 2) as net_churn_rate_percent,
  round(100.0 * b.moveout_count / nullif(t.total_moveouts, 0), 2) as moveout_share_percent,
  round(100.0 * b.movein_count / nullif(t.total_moveins, 0), 2) as movein_share_percent,
  round(100.0 * b.moveout_count / nullif(b.moveout_count + b.movein_count, 0), 2) as outflow_pressure_percent,
  round(greatest(12.0, least(56.0, sqrt(b.moveout_count) * 2.8)), 2) as bubble_size
from base b
cross join totals t
order by b.band_order
```

```sql pricing_ratio_kpis
with ratio as (
  select
    rent_band,
    movein_count,
    moveout_count,
    case rent_band
      when '<50k' then 1
      when '50-59k' then 2
      when '60-69k' then 3
      when '70-79k' then 4
      when '80k+' then 5
      else 99
    end as band_order,
    round(100.0 * movein_count / nullif(moveout_count, 0), 2) as replacement_rate_pct,
    round(100.0 * (moveout_count - movein_count) / nullif(moveout_count, 0), 2) as net_churn_rate_pct
  from snapshot_csv.rent_band_inout_balance
),
totals as (
  select
    round(100.0 * sum(movein_count) / nullif(sum(moveout_count), 0), 2) as overall_replacement_rate_percent,
    round(100.0 * (sum(moveout_count) - sum(movein_count)) / nullif(sum(moveout_count), 0), 2) as overall_churn_pressure_percent
  from ratio
),
worst as (
  select rent_band, replacement_rate_pct
  from ratio
  order by replacement_rate_pct asc, moveout_count desc
  limit 1
),
largest as (
  select
    rent_band,
    round(100.0 * moveout_count / nullif((select sum(moveout_count) from ratio), 0), 2) as moveout_share_pct
  from ratio
  order by moveout_count desc
  limit 1
)
select
  t.overall_replacement_rate_percent,
  t.overall_churn_pressure_percent,
  w.rent_band as worst_replacement_band,
  w.replacement_rate_pct as worst_replacement_rate_percent,
  l.rent_band as largest_outflow_band,
  l.moveout_share_pct as largest_outflow_share_percent
from totals t
cross join worst w
cross join largest l
```

```sql rent_band_risk_heatmap
with ratio as (
  select
    rent_band,
    case rent_band
      when '<50k' then 1
      when '50-59k' then 2
      when '60-69k' then 3
      when '70-79k' then 4
      when '80k+' then 5
      else 99
    end as band_order,
    round(100.0 * movein_count / nullif(moveout_count, 0), 2) as replacement_rate_pct,
    round(100.0 * (moveout_count - movein_count) / nullif(moveout_count, 0), 2) as net_churn_rate_pct,
    round(100.0 * moveout_count / nullif(moveout_count + movein_count, 0), 2) as outflow_pressure_pct
  from snapshot_csv.rent_band_inout_balance
),
totals as (
  select sum(moveout_count) as total_moveouts
  from snapshot_csv.rent_band_inout_balance
),
enriched as (
  select
    r.rent_band,
    r.band_order,
    round(100.0 - r.replacement_rate_pct, 2) as replacement_gap_pct,
    r.net_churn_rate_pct,
    round(
      100.0 * b.moveout_count / nullif((select total_moveouts from totals), 0),
      2
    ) as moveout_share_pct
  from ratio r
  join snapshot_csv.rent_band_inout_balance b
    on b.rent_band = r.rent_band
)
select
  rent_band,
  band_order,
  metric_label,
  metric_order,
  metric_value
from (
  select rent_band, band_order, 'Replacement Gap %' as metric_label, 1 as metric_order, replacement_gap_pct as metric_value from enriched
  union all
  select rent_band, band_order, 'Net Churn %' as metric_label, 2 as metric_order, net_churn_rate_pct as metric_value from enriched
  union all
  select rent_band, band_order, 'Move-out Share %' as metric_label, 3 as metric_order, moveout_share_pct as metric_value from enriched
) t
order by metric_order, band_order
```

```sql occ_rent_band_current
select
  feature_value as rent_band,
  occupied_rooms,
  total_rooms,
  round(occupancy_rate * 100, 2) as occupancy_rate_percent
from snapshot_csv.occupancy_by_room_feature
where timepoint_label = 'Current'
  and feature_group = 'rent_band'
order by case feature_value
  when '<50k' then 1
  when '50-59k' then 2
  when '60-69k' then 3
  when '70-79k' then 4
  when '80k+' then 5
  else 99
end
```

```sql occ_floor_current
select
  feature_value as room_floor,
  occupied_rooms,
  total_rooms,
  round(occupancy_rate * 100, 2) as occupancy_rate_percent
from snapshot_csv.occupancy_by_room_feature
where timepoint_label = 'Current'
  and feature_group = 'room_floor'
order by try_cast(feature_value as integer) asc nulls last
```

```sql property_risk
select *
from snapshot_csv.property_risk_rank
order by risk_score desc, moveout_count desc
```

```sql property_price_gap
select
  property_norm,
  municipality,
  movein_count,
  moveout_count,
  net_change,
  avg_movein_rent,
  avg_moveout_rent,
  price_gap_avg_rent
from snapshot_csv.property_risk_rank
where movein_count > 0 or moveout_count > 0
order by abs(price_gap_avg_rent) desc, risk_score desc
limit 40
```

```sql pricing_bullets
select *
from snapshot_csv.insight_bullets
where theme in ('Demand Pressure', 'Pricing Risk', 'Property Churn')
order by priority
```

<Grid cols={2} gapSize="md">
  <BigValue data={pricing_ratio_kpis} title="Overall Replacement Rate (%)" value="overall_replacement_rate_percent" fmt="num2" />
  <BigValue data={pricing_ratio_kpis} title="Overall Churn Pressure (%)" value="overall_churn_pressure_percent" fmt="num2" />
</Grid>

<ul>
  <li>
    Weakest replacement band: <strong>{pricing_ratio_kpis[0].worst_replacement_band}</strong>
    ({pricing_ratio_kpis[0].worst_replacement_rate_percent}%).
  </li>
  <li>
    Largest outflow concentration: <strong>{pricing_ratio_kpis[0].largest_outflow_band}</strong>
    ({pricing_ratio_kpis[0].largest_outflow_share_percent}% of all move-outs).
  </li>
</ul>

## Rent-Band Risk Map (Exposure vs Replacement)

<ECharts
  data={rent_band_ratio_profile}
  config={{
    title: { text: 'Bubble size = move-out volume; Y axis = replacement rate', left: 'center' },
    tooltip: { trigger: 'item' },
    xAxis: { type: 'value', name: 'Move-out Share (%)', min: 0, max: 40 },
    yAxis: { type: 'value', name: 'Replacement Rate (%)', min: 0, max: 110 },
    series: [
      {
        type: 'scatter',
        data: rent_band_ratio_profile.map((d) => ({
          name: d.rent_band,
          value: [d.moveout_share_percent, d.replacement_rate_percent, d.bubble_size],
          itemStyle: {
            color:
              d.replacement_rate_percent >= 80
                ? '#1a9850'
                : d.replacement_rate_percent >= 60
                ? '#91cf60'
                : d.replacement_rate_percent >= 40
                ? '#fee08b'
                : d.replacement_rate_percent >= 20
                ? '#fc8d59'
                : '#d73027'
          }
        })),
        symbolSize: (v) => v[2],
        label: { show: true, formatter: '{b}', position: 'top' },
        markLine: {
          symbol: 'none',
          lineStyle: { type: 'dashed', color: '#666' },
          data: [{ yAxis: 100, name: 'Full replacement' }, { yAxis: 60, name: 'Watchline' }]
        }
      }
    ]
  }}
/>

## Rent-Band Risk Heatmap (Higher = Worse)

<ECharts
  data={rent_band_risk_heatmap}
  config={{
    tooltip: { position: 'top' },
    grid: { top: '15%', left: '10%', right: '6%', height: '60%' },
    xAxis: {
      type: 'category',
      data: rent_band_ratio_profile.map((d) => d.rent_band)
    },
    yAxis: {
      type: 'category',
      data: ['Replacement Gap %', 'Net Churn %', 'Move-out Share %']
    },
    visualMap: {
      min: 0,
      max: 100,
      calculable: true,
      orient: 'horizontal',
      left: 'center',
      bottom: 0,
      inRange: { color: ['#1a9850', '#fee08b', '#d73027'] }
    },
    series: [
      {
        name: 'Risk',
        type: 'heatmap',
        data: rent_band_risk_heatmap.map((d) => [d.rent_band, d.metric_label, d.metric_value]),
        label: { show: true, formatter: '{c}%' }
      }
    ]
  }}
/>

## Portfolio Mix Shift (Move-in Share vs Move-out Share)

<ECharts
  data={rent_band_ratio_profile}
  config={{
    legend: { bottom: 0 },
    tooltip: {},
    radar: {
      indicator: rent_band_ratio_profile.map((d) => ({
        name: d.rent_band,
        max: 40
      })),
      radius: '62%'
    },
    series: [
      {
        type: 'radar',
        data: [
          {
            name: 'Move-in Share %',
            value: rent_band_ratio_profile.map((d) => d.movein_share_percent)
          },
          {
            name: 'Move-out Share %',
            value: rent_band_ratio_profile.map((d) => d.moveout_share_percent)
          }
        ]
      }
    ]
  }}
/>

## Rent-Band Ratio Table

<DataTable data={rent_band_ratio_profile} downloadable={true} />

## Current Occupancy by Rent Band (Rooms)

<DataTable data={occ_rent_band_current} downloadable={true} />

## Current Occupancy by Floor (Rooms)

<DataTable data={occ_floor_current} downloadable={true} />

## Property Risk Ranking

<DataTable data={property_risk} downloadable={true} />

## Price Gap Opportunities

<DataTable data={property_price_gap} downloadable={true} />

## Recommended Actions

<ul>
  {#each pricing_bullets as b}
    <li>
      <strong>{b.theme}</strong>: {b.observation} ({b.evidence_metric})<br />
      {b.recommended_action}
    </li>
  {/each}
</ul>
