





with validation_errors as (

    select
        activity_date, tenant_type
    from `tokyobeta_analytics`.`daily_activity_summary`
    group by activity_date, tenant_type
    having count(*) > 1

)

select *
from validation_errors


