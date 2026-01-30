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
        from `tokyobeta_test_results`.`not_null_moveout_notices_notice_received_date`
    
      
    ) dbt_internal_test