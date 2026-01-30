
    
    

with all_values as (

    select
        moveout_status as value_field,
        count(*) as n_records

    from `tokyobeta_analytics`.`moveout_notices`
    group by moveout_status

)

select *
from all_values
where value_field not in (
    'Completed','Pending'
)


