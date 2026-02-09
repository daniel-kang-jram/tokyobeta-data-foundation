
    
    

with all_values as (

    select
        rent_range_order as value_field,
        count(*) as n_records

    from `gold`.`moveout_analysis`
    group by rent_range_order

)

select *
from all_values
where value_field not in (
    '1','2','3','4','5'
)


