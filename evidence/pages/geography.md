# Geography & Property Breakdown

```sql occupancy_map
select *
from aurora_gold.occupancy_property_map_latest
```

## Tokyo Occupancy Map (Latest Snapshot)

<BubbleMap
  data={occupancy_map}
  lat="latitude"
  long="longitude"
  size="total_rooms_num0"
  value="occupancy_rate_pct"
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
/>

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

## Municipality hotspots (weekly, last 12 weeks)

<Tabs background="true">
  <Tab label="Net change" id="muni-net">
    <BarChart
      data={municipality_totals}
      x=municipality
      y=net_change
      swapXY={true}
      chartAreaHeight={900}
      title="Municipality Net Change (Top Absolute)"
    />
  </Tab>
  <Tab label="Move-ins" id="muni-in">
    <BarChart
      data={municipality_totals}
      x=municipality
      y=movein_count
      swapXY={true}
      chartAreaHeight={900}
      title="Municipality Move-ins (Top)"
    />
  </Tab>
  <Tab label="Move-outs" id="muni-out">
    <BarChart
      data={municipality_totals}
      x=municipality
      y=moveout_count
      swapXY={true}
      chartAreaHeight={900}
      title="Municipality Move-outs (Top)"
    />
  </Tab>
</Tabs>

## Property hotspots (weekly, last 12 weeks)

<Tabs background="true">
  <Tab label="Net change" id="prop-net">
    <BarChart
      data={property_totals}
      x=apartment_name
      y=net_change
      swapXY={true}
      chartAreaHeight={900}
      title="Property Net Change (Top Absolute)"
    />
  </Tab>
  <Tab label="Move-ins" id="prop-in">
    <BarChart
      data={property_totals}
      x=apartment_name
      y=movein_count
      swapXY={true}
      chartAreaHeight={900}
      title="Property Move-ins (Top)"
    />
  </Tab>
  <Tab label="Move-outs" id="prop-out">
    <BarChart
      data={property_totals}
      x=apartment_name
      y=moveout_count
      swapXY={true}
      chartAreaHeight={900}
      title="Property Move-outs (Top)"
    />
  </Tab>
</Tabs>

## Municipality weekly detail

<DataTable data={municipality_churn} />

## Property weekly detail

<DataTable data={property_churn} />
