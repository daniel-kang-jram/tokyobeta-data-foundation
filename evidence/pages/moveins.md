# Move-in Profiling

```sql movein_total_monthly
select
  month_start,
  sum(movein_count) as movein_count
from aurora_gold.movein_profile_monthly
group by month_start
order by month_start
```

```sql movein_monthly
select *
from aurora_gold.movein_profile_monthly
order by month_start
```

## Move-ins trend (all segments)

<LineChart data={movein_total_monthly} x=month_start y=movein_count title="Total Move-ins (Monthly)" />

```sql movein_by_tenant_type
select
  month_start,
  tenant_type,
  sum(movein_count) as movein_count
from aurora_gold.movein_profile_monthly
group by month_start, tenant_type
order by month_start, tenant_type
```

```sql movein_top_nationality
select
  nationality,
  sum(movein_count) as movein_count
from aurora_gold.movein_profile_monthly
group by nationality
order by movein_count desc
limit 20
```

## Monthly move-ins by contract type

<BarChart data={movein_by_tenant_type} x=month_start y=movein_count series=tenant_type title="Move-ins by Tenant Type" />

## Top nationalities (move-ins)

<BarChart data={movein_top_nationality} x=nationality y=movein_count title="Top Move-in Nationalities" />

## Detailed breakdown (municipality, property, nationality)

<DataTable data={movein_monthly} />
