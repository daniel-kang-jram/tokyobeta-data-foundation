
    
    

with all_values as (

    select
        rent_range as value_field,
        count(*) as n_records

    from `gold`.`moveout_analysis`
    group by rent_range

)

select *
from all_values
where value_field not in (
    'Under 50K','50K-70K','70K-100K','100K-150K','150K+'
)


