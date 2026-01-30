
    
    

with all_values as (

    select
        tenant_type as value_field,
        count(*) as n_records

    from `tokyobeta_analytics`.`new_contracts`
    group by tenant_type

)

select *
from all_values
where value_field not in (
    'individual','corporate'
)


