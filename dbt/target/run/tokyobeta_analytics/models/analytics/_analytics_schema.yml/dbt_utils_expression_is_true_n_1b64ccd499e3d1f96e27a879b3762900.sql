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
        from `tokyobeta_test_results`.`dbt_utils_expression_is_true_n_1b64ccd499e3d1f96e27a879b3762900`
    
      
    ) dbt_internal_test