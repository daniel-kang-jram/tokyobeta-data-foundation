# Move-out Profiling

```sql moveout_total_monthly
select
  month_start,
  sum(moveout_count) as moveout_count
from aurora_gold.moveout_profile_monthly
group by month_start
order by month_start
```

```sql moveout_monthly
select *
from aurora_gold.moveout_profile_monthly
order by month_start
```

## Move-outs trend (all segments)

<LineChart data={moveout_total_monthly} x=month_start y=moveout_count title="Total Move-outs (Monthly)" />

```sql moveout_by_tenant_type
select
  month_start,
  tenant_type,
  sum(moveout_count) as moveout_count
from aurora_gold.moveout_profile_monthly
group by month_start, tenant_type
order by month_start, tenant_type
```

```sql moveout_top_nationality
select
  nationality,
  sum(moveout_count) as moveout_count
from aurora_gold.moveout_profile_monthly
group by nationality
order by moveout_count desc
limit 20
```

## Monthly move-outs by contract type

<BarChart data={moveout_by_tenant_type} x=month_start y=moveout_count series=tenant_type title="Move-outs by Tenant Type" />

## Top nationalities (move-outs)

<BarChart data={moveout_top_nationality} x=nationality y=moveout_count title="Top Move-out Nationalities" />

## Detailed breakdown (municipality, property, nationality)

<DataTable data={moveout_monthly} />
