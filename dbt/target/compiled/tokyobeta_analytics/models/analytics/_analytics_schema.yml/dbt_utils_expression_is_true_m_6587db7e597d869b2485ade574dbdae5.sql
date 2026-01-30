



select
    *
from `tokyobeta_analytics`.`moveout_notices`

where not(notice_received_date >= DATE_SUB(CURRENT_DATE, INTERVAL 24 MONTH))

