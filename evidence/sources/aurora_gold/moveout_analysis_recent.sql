SELECT *
FROM gold.moveout_analysis
WHERE moveout_date >= DATE_SUB(CURDATE(), INTERVAL 365 DAY)
ORDER BY moveout_date DESC, rent_range_order, asset_id_hj;

