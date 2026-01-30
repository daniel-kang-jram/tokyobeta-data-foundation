



select
    *
from `tokyobeta_analytics`.`daily_activity_summary`

where not(applications_count >= 0)

