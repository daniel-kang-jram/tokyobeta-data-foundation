



select
    *
from (select * from `tokyobeta_analytics`.`moveout_notices` where planned_moveout_date IS NOT NULL) dbt_subquery

where not(notice_lead_time_days >= 0)

