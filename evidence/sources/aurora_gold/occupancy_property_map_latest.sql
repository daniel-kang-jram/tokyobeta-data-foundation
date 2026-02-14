SELECT
  snapshot_date,
  asset_id_hj,
  apartment_name,
  municipality,
  prefecture,
  latitude,
  longitude,
  CAST(total_rooms AS SIGNED) AS total_rooms_num0,
  CAST(occupied_rooms AS SIGNED) AS occupied_rooms_num0,
  CAST(occupancy_rate AS DECIMAL(10,6)) AS occupancy_rate_pct,
  CAST(occupancy_rate_7d_ago AS DECIMAL(10,6)) AS occupancy_rate_7d_ago_pct,
  CAST(occupancy_rate_delta_7d * 100.0 AS DECIMAL(10,3)) AS occupancy_rate_delta_7d_pp,
  CAST(occupied_rooms_7d_ago AS SIGNED) AS occupied_rooms_7d_ago_num0,
  CAST(occupied_rooms_delta_7d AS SIGNED) AS occupied_rooms_delta_7d_num0
FROM gold.occupancy_property_map_latest
WHERE latitude IS NOT NULL
  AND longitude IS NOT NULL;

