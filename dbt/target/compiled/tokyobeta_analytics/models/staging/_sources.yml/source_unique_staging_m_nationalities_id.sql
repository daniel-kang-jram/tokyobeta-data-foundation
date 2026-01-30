
    
    

select
    id as unique_field,
    count(*) as n_records

from `staging`.`m_nationalities`
where id is not null
group by id
having count(*) > 1


