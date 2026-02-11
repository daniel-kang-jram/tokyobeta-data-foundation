# Geography & Property Breakdown

```sql municipality_churn
select *
from aurora_gold.municipality_churn_monthly
order by month_start, net_change desc
```

```sql property_churn
select *
from aurora_gold.property_churn_monthly
order by month_start, net_change desc
```

```sql municipality_totals
select
  municipality,
  sum(movein_count) as movein_count,
  sum(moveout_count) as moveout_count,
  sum(movein_count) - sum(moveout_count) as net_change
from aurora_gold.municipality_churn_monthly
group by municipality
order by abs(sum(movein_count) - sum(moveout_count)) desc
limit 30
```

```sql property_totals
select
  apartment_name,
  sum(movein_count) as movein_count,
  sum(moveout_count) as moveout_count,
  sum(movein_count) - sum(moveout_count) as net_change
from aurora_gold.property_churn_monthly
group by apartment_name
order by abs(sum(movein_count) - sum(moveout_count)) desc
limit 30
```

## Municipality net change hotspots

<BarChart data={municipality_totals} x=municipality y=net_change title="Municipality Net Change (Top Absolute)" />

## Property net change hotspots

<BarChart data={property_totals} x=apartment_name y=net_change title="Property Net Change (Top Absolute)" />

## Municipality monthly detail

<DataTable data={municipality_churn} />

## Property monthly detail

<DataTable data={property_churn} />
