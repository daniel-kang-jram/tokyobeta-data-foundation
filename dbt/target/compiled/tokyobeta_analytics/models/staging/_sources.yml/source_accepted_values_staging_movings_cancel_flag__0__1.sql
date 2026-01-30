
    
    

with all_values as (

    select
        cancel_flag as value_field,
        count(*) as n_records

    from `staging`.`movings`
    group by cancel_flag

)

select *
from all_values
where value_field not in (
    '0','1'
)


