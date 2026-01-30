
    
    

with all_values as (

    select
        is_moveout as value_field,
        count(*) as n_records

    from `staging`.`movings`
    group by is_moveout

)

select *
from all_values
where value_field not in (
    '0','1'
)


