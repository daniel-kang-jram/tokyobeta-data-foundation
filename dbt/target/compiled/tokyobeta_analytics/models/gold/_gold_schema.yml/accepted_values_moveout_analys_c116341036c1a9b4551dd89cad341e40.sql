
    
    

with all_values as (

    select
        tenure_category as value_field,
        count(*) as n_records

    from `gold`.`moveout_analysis`
    group by tenure_category

)

select *
from all_values
where value_field not in (
    'Short (<6mo)','Medium (6-12mo)','Long (1-2yr)','Very Long (2yr+)','Unknown'
)


