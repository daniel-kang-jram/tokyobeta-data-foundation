
    
    

with all_values as (

    select
        tenant_type as value_field,
        count(*) as n_records

    from `gold`.`moveout_summary`
    group by tenant_type

)

select *
from all_values
where value_field not in (
    'individual','corporate'
)


