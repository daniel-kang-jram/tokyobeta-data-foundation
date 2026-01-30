



select
    *
from (select * from `tokyobeta_analytics`.`new_contracts` where age IS NOT NULL) dbt_subquery

where not(age BETWEEN 18 AND 100)

