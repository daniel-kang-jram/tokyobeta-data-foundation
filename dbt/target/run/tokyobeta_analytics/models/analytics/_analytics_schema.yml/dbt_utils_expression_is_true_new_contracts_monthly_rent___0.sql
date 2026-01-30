select
      count(*) as failures,
      case
        when count(*) >10 then 'true'
        else 'false'
      end as should_warn,
      case
        when count(*) >50 then 'true'
        else 'false'
      end as should_error
    from (
      
        select *
        from `tokyobeta_test_results`.`dbt_utils_expression_is_true_new_contracts_monthly_rent___0`
    
      
    ) dbt_internal_test