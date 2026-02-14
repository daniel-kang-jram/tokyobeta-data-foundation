SELECT *
FROM gold.movein_analysis
WHERE contract_start_date >= DATE_SUB(CURDATE(), INTERVAL 365 DAY)
ORDER BY contract_start_date DESC, asset_id_hj, room_number;

