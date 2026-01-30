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
        from `tokyobeta_test_results`.`dbt_utils_expression_is_true_n_18b9850f49710f69d63470e3fd5e6e1b`
    
      
    ) dbt_internal_test