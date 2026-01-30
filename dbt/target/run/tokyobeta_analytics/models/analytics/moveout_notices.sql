
      insert into `tokyobeta_analytics`.`moveout_notices` (`contract_id`, `tenant_id`, `asset_id_hj`, `room_number`, `contract_system`, `contract_channel`, `original_contract_date`, `contract_date`, `contract_start_date`, `rent_start_date`, `contract_expiration_date`, `notice_received_date`, `planned_moveout_date`, `renewal_flag`, `monthly_rent`, `tenant_type`, `gender`, `age`, `nationality`, `occupation_company`, `residence_status`, `latitude`, `longitude`, `prefecture`, `municipality`, `full_address`, `notice_lead_time_days`, `moveout_status`, `created_at`, `updated_at`)
    (
       select `contract_id`, `tenant_id`, `asset_id_hj`, `room_number`, `contract_system`, `contract_channel`, `original_contract_date`, `contract_date`, `contract_start_date`, `rent_start_date`, `contract_expiration_date`, `notice_received_date`, `planned_moveout_date`, `renewal_flag`, `monthly_rent`, `tenant_type`, `gender`, `age`, `nationality`, `occupation_company`, `residence_status`, `latitude`, `longitude`, `prefecture`, `municipality`, `full_address`, `notice_lead_time_days`, `moveout_status`, `created_at`, `updated_at`
       from `tokyobeta_analytics`.`moveout_notices__dbt_tmp`
    )
  