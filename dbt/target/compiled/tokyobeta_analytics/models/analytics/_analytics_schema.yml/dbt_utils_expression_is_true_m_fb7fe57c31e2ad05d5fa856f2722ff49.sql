



select
    *
from `tokyobeta_analytics`.`moveouts`

where not(moveout_date >= contract_start_date)

