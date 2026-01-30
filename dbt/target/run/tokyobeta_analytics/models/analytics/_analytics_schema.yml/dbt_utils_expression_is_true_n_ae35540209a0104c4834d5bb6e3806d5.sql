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
        from `tokyobeta_test_results`.`dbt_utils_expression_is_true_n_ae35540209a0104c4834d5bb6e3806d5`
    
      
    ) dbt_internal_test