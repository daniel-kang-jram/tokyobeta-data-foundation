select
      count(*) as failures,
      case
        when count(*) <> 0 then 'true'
        else 'false'
      end as should_warn,
      case
        when count(*) >100 then 'true'
        else 'false'
      end as should_error
    from (
      
        select *
        from `tokyobeta_test_results`.`dbt_utils_expression_is_true_m_6587db7e597d869b2485ade574dbdae5`
    
      
    ) dbt_internal_test