select
      count(*) as failures,
      case
        when count(*) <> 0 then 'true'
        else 'false'
      end as should_warn,
      case
        when count(*) <> 0 then 'true'
        else 'false'
      end as should_error
    from (
      
        select *
        from `tokyobeta_test_results`.`assert_referential_integrity`
    
      
    ) dbt_internal_test