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
        from `tokyobeta_test_results`.`accepted_values_daily_activity_913de4493a74d7ae0c7c24e39f22f8d3`
    
      
    ) dbt_internal_test