# Geography & Property Breakdown

```sql occupancy_map
select
  *,
  least(greatest(total_rooms_num0, 1), 20) as point_size
from aurora_gold.occupancy_property_map_latest
```

```sql occupancy_map_coverage
select
  substr(cast(min(snapshot_date) as varchar), 1, 10) as coverage_from,
  substr(cast(max(snapshot_date) as varchar), 1, 10) as coverage_to,
  substr(cast(max(snapshot_date) as varchar), 1, 10) as freshness_snapshot_date
from aurora_gold.occupancy_property_map_latest
```

## Tokyo Occupancy Map (Latest Snapshot)

<BubbleMap
  data={occupancy_map}
  lat="latitude"
  long="longitude"
  size="point_size"
  sizeCol="point_size"
  maxSize={5}
  pointStyle="points"
  value="occupancy_rate_pct"
  opacity={0.95}
  ignoreZoom={true}
  stroke={false}
  weight={0}
  pointName="apartment_name"
  legendType="scalar"
  height={460}
  startingLat={35.68}
  startingLong={139.76}
  startingZoom={10}
  tooltip={[
    { id: "apartment_name", showColumnName: false, valueClass: "font-bold text-sm" },
    { id: "municipality" },
    { id: "occupied_rooms_num0", fmt: "num0" },
    { id: "total_rooms_num0", fmt: "num0" },
    { id: "occupancy_rate_pct", fmt: "pct" },
    { id: "occupancy_rate_delta_7d_pp", fmt: "num2" }
  ]}
  colorPalette={['#b91c1c', '#f59e0b', '#22c55e']}
/>

<Note>
Time basis: latest property snapshot.
Coverage: {occupancy_map_coverage[0].coverage_from} to {occupancy_map_coverage[0].coverage_to}.
Freshness: {occupancy_map_coverage[0].freshness_snapshot_date}.
</Note>

```sql municipality_churn
select *
from aurora_gold.municipality_churn_weekly
order by week_start, net_change desc
```

```sql property_churn
select *
from aurora_gold.property_churn_weekly
order by week_start, net_change desc
```

```sql municipality_totals
select
  municipality,
  sum(movein_count) as movein_count,
  sum(moveout_count) as moveout_count,
  sum(net_change) as net_change
from aurora_gold.municipality_churn_weekly
where week_start >= CURRENT_DATE - INTERVAL 12 WEEK
group by municipality
order by abs(sum(net_change)) desc
limit 30
```

```sql property_totals
select
  apartment_name,
  sum(movein_count) as movein_count,
  sum(moveout_count) as moveout_count,
  sum(net_change) as net_change
from aurora_gold.property_churn_weekly
where week_start >= CURRENT_DATE - INTERVAL 12 WEEK
group by apartment_name
order by abs(sum(net_change)) desc
limit 30
```

```sql municipality_hotspot_coverage
select
  substr(cast(min(week_start) as varchar), 1, 10) as coverage_from,
  substr(cast(max(week_start) as varchar), 1, 10) as coverage_to,
  substr(cast(max(week_start) as varchar), 1, 10) as freshness_week_start
from aurora_gold.municipality_churn_weekly
where week_start >= CURRENT_DATE - INTERVAL 12 WEEK
```

```sql property_hotspot_coverage
select
  substr(cast(min(week_start) as varchar), 1, 10) as coverage_from,
  substr(cast(max(week_start) as varchar), 1, 10) as coverage_to,
  substr(cast(max(week_start) as varchar), 1, 10) as freshness_week_start
from aurora_gold.property_churn_weekly
where week_start >= CURRENT_DATE - INTERVAL 12 WEEK
```

```sql municipality_detail_coverage
select
  substr(cast(min(week_start) as varchar), 1, 10) as coverage_from,
  substr(cast(max(week_start) as varchar), 1, 10) as coverage_to,
  substr(cast(max(week_start) as varchar), 1, 10) as freshness_week_start
from aurora_gold.municipality_churn_weekly
```

```sql property_detail_coverage
select
  substr(cast(min(week_start) as varchar), 1, 10) as coverage_from,
  substr(cast(max(week_start) as varchar), 1, 10) as coverage_to,
  substr(cast(max(week_start) as varchar), 1, 10) as freshness_week_start
from aurora_gold.property_churn_weekly
```

## Municipality hotspots (weekly, last 12 weeks)

<Tabs background="true">
  <Tab label="Net change" id="muni-net">
    <BarChart
      data={municipality_totals}
      x=municipality
      y=net_change
      swapXY={true}
      chartAreaHeight={520}
      title="Municipality Net Change (Top Absolute)"
    />
  </Tab>
  <Tab label="Move-ins" id="muni-in">
    <BarChart
      data={municipality_totals}
      x=municipality
      y=movein_count
      swapXY={true}
      chartAreaHeight={520}
      title="Municipality Move-ins (Top)"
    />
  </Tab>
  <Tab label="Move-outs" id="muni-out">
    <BarChart
      data={municipality_totals}
      x=municipality
      y=moveout_count
      swapXY={true}
      chartAreaHeight={520}
      title="Municipality Move-outs (Top)"
    />
  </Tab>
</Tabs>

<Note>
Time basis: weekly municipality hotspot totals (last 12 weeks).
Coverage: {municipality_hotspot_coverage[0].coverage_from} to {municipality_hotspot_coverage[0].coverage_to}.
Freshness: {municipality_hotspot_coverage[0].freshness_week_start}.
</Note>

## Property hotspots (weekly, last 12 weeks)

<Tabs background="true">
  <Tab label="Net change" id="prop-net">
    <BarChart
      data={property_totals}
      x=apartment_name
      y=net_change
      swapXY={true}
      chartAreaHeight={520}
      title="Property Net Change (Top Absolute)"
    />
  </Tab>
  <Tab label="Move-ins" id="prop-in">
    <BarChart
      data={property_totals}
      x=apartment_name
      y=movein_count
      swapXY={true}
      chartAreaHeight={520}
      title="Property Move-ins (Top)"
    />
  </Tab>
  <Tab label="Move-outs" id="prop-out">
    <BarChart
      data={property_totals}
      x=apartment_name
      y=moveout_count
      swapXY={true}
      chartAreaHeight={520}
      title="Property Move-outs (Top)"
    />
  </Tab>
</Tabs>

<Note>
Time basis: weekly property hotspot totals (last 12 weeks).
Coverage: {property_hotspot_coverage[0].coverage_from} to {property_hotspot_coverage[0].coverage_to}.
Freshness: {property_hotspot_coverage[0].freshness_week_start}.
</Note>

## Municipality weekly detail

<DataTable data={municipality_churn} downloadable={true} />

<Note>
Time basis: weekly municipality detail rows.
Coverage: {municipality_detail_coverage[0].coverage_from} to {municipality_detail_coverage[0].coverage_to}.
Freshness: {municipality_detail_coverage[0].freshness_week_start}.
</Note>

## Property weekly detail

<DataTable data={property_churn} downloadable={true} />

<Note>
Time basis: weekly property detail rows.
Coverage: {property_detail_coverage[0].coverage_from} to {property_detail_coverage[0].coverage_to}.
Freshness: {property_detail_coverage[0].freshness_week_start}.
</Note>
