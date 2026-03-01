from __future__ import annotations

from datetime import date, datetime, time
from typing import Dict

from scripts.flash_report_fill.types import FlashReportQueryConfig, QuerySpec


CORPORATE_CODES = (2, 3)
INDIVIDUAL_CODES = (1, 6, 7, 9)

ACTIVE_OCCUPANCY_STATUSES = (7, 9, 10, 11, 12, 13, 14, 15)
PLANNED_MOVEIN_STATUSES = (4, 5, 6, 7, 9, 10, 11, 12, 13, 14, 15)
COMPLETED_MOVEIN_STATUSES = (4, 5, 6, 7, 9, 10, 11, 12, 13, 14, 15)
COMPLETED_MOVEOUT_STATUSES = (14, 15, 16, 17)
PLANNED_MOVEOUT_STATUSES = (14, 15, 16, 17)

DEFAULT_MOVEIN_PREDICTION_COLUMN = "original_movein_date"
DEFAULT_MOVEOUT_PREDICTION_COLUMN = "moveout_date"
SUPPORTED_MOVEIN_PREDICTION_COLUMNS = ("movein_date", "original_movein_date", "movein_decided_date")
SUPPORTED_MOVEOUT_PREDICTION_COLUMNS = ("moveout_date", "moveout_plans_date", "moveout_date_integrated")

TENANT_TYPE_CASE_TEMPLATE = """
CASE
    WHEN {alias}.moving_agreement_type IN (2, 3) THEN 'corporate'
    WHEN {alias}.moving_agreement_type IN (1, 6, 7, 9) THEN 'individual'
    ELSE 'unknown'
END
""".strip()

ROOM_PRIORITY_CASE = """
CASE management_status_code
    WHEN 9 THEN 1
    WHEN 10 THEN 2
    WHEN 11 THEN 3
    WHEN 12 THEN 4
    WHEN 13 THEN 5
    WHEN 14 THEN 6
    WHEN 15 THEN 7
    WHEN 7 THEN 8
    WHEN 6 THEN 9
    WHEN 5 THEN 10
    WHEN 4 THEN 11
    ELSE 12
END
""".strip()

BASE_CONTRACTS_CTE = """
WITH base_contracts AS (
    SELECT
        m.id AS moving_id,
        m.tenant_id,
        m.apartment_id,
        m.room_id,
        m.movein_date,
        m.original_movein_date,
        m.movein_decided_date,
        m.moveout_date,
        m.moveout_plans_date,
        m.moveout_date_integrated,
        m.move_renew_flag,
        m.updated_at,
        m.moving_agreement_type,
        COALESCE(m.cancel_flag, 0) AS cancel_flag,
        COALESCE(m.is_moveout, 0) AS is_moveout,
        t.status AS management_status_code
    FROM staging.movings m
    INNER JOIN staging.tenants t
        ON m.tenant_id = t.id
    WHERE COALESCE(m.cancel_flag, 0) = 0
),
classified AS (
    SELECT
        c.*,
        CONCAT(c.apartment_id, '-', c.room_id) AS room_key,
        COALESCE(c.moveout_plans_date, c.moveout_date) AS effective_moveout_at,
        {tenant_type_case} AS tenant_type
    FROM base_contracts c
)
""".strip().format(tenant_type_case=TENANT_TYPE_CASE_TEMPLATE.format(alias="c"))


def classify_tenant_type(contract_code: int | None) -> str:
    """Classify moving agreement type into report tenant type."""
    if contract_code in CORPORATE_CODES:
        return "corporate"
    if contract_code in INDIVIDUAL_CODES:
        return "individual"
    return "unknown"


def _to_datetime(value: datetime | date) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.combine(value, time.min)


def is_active_at_snapshot(
    move_in_at: datetime | date | None,
    move_out_at: datetime | date | None,
    snapshot_ts: datetime,
) -> bool:
    """Apply strict active-at-snapshot rule: move_out must be strictly greater."""
    if move_in_at is None:
        return False

    move_in_dt = _to_datetime(move_in_at)
    if snapshot_ts.tzinfo is not None and move_in_dt.tzinfo is None:
        move_in_dt = move_in_dt.replace(tzinfo=snapshot_ts.tzinfo)
    if move_in_dt > snapshot_ts:
        return False

    if move_out_at is None:
        return True

    move_out_dt = _to_datetime(move_out_at)
    if snapshot_ts.tzinfo is not None and move_out_dt.tzinfo is None:
        move_out_dt = move_out_dt.replace(tzinfo=snapshot_ts.tzinfo)
    return move_out_dt > snapshot_ts


def _validate_prediction_column(column: str, allowed: tuple[str, ...], kind: str) -> str:
    if column not in allowed:
        allowed_str = ", ".join(allowed)
        raise ValueError(f"Unsupported {kind} column: {column}. Allowed: {allowed_str}")
    return column


def _build_metric_sql(where_clause: str, result_select_sql: str) -> str:
    """Build metric SQL with deduplication applied after metric-specific filtering."""
    return f"""
{BASE_CONTRACTS_CTE},
filtered_contracts AS (
    SELECT *
    FROM classified
    WHERE {where_clause}
),
deduplicated_filtered_contracts AS (
    SELECT
        f.*,
        ROW_NUMBER() OVER (
            PARTITION BY f.tenant_id, f.apartment_id, f.room_id
            ORDER BY f.movein_date DESC, f.updated_at DESC, f.moving_id DESC
        ) AS rn
    FROM filtered_contracts f
)
{result_select_sql}
""".strip()


def _build_d5_fact_aligned_sql() -> str:
    return f"""
{BASE_CONTRACTS_CTE},
filtered_contracts AS (
    SELECT *
    FROM classified
    WHERE is_moveout = 0
      AND management_status_code IN {ACTIVE_OCCUPANCY_STATUSES}
      AND (
          management_status_code <> 7
          OR movein_date < %(snapshot_start)s
      )
),
deduplicated_filtered_contracts AS (
    SELECT
        f.*,
        ROW_NUMBER() OVER (
            PARTITION BY f.tenant_id, f.apartment_id, f.room_id
            ORDER BY f.movein_date DESC, f.updated_at DESC, f.moving_id DESC
        ) AS rn_tenant_room
    FROM filtered_contracts f
),
latest_tenant_room AS (
    SELECT *
    FROM deduplicated_filtered_contracts
    WHERE rn_tenant_room = 1
),
room_priority AS (
    SELECT
        l.*,
        ROW_NUMBER() OVER (
            PARTITION BY apartment_id, room_id
            ORDER BY
                {ROOM_PRIORITY_CASE},
                movein_date DESC,
                updated_at DESC,
                moving_id DESC
        ) AS room_priority_rn
    FROM latest_tenant_room l
)
SELECT
    COUNT(DISTINCT room_key) AS occupied_rooms
FROM room_priority
WHERE room_priority_rn = 1
""".strip()


def build_metric_queries(config: FlashReportQueryConfig | None = None) -> Dict[str, QuerySpec]:
    """Build decision-complete SQL specs for all flash report metrics."""
    query_config = config or FlashReportQueryConfig()
    movein_prediction_date_column = _validate_prediction_column(
        query_config.movein_prediction_date_column,
        SUPPORTED_MOVEIN_PREDICTION_COLUMNS,
        "move-in prediction",
    )
    moveout_prediction_date_column = _validate_prediction_column(
        query_config.moveout_prediction_date_column,
        SUPPORTED_MOVEOUT_PREDICTION_COLUMNS,
        "move-out prediction",
    )

    def split_moveins(
        window_start_param: str, window_end_param: str, status_tuple: tuple[int, ...]
    ) -> str:
        _ = status_tuple  # Completed move-ins are event/date driven, not current-status driven.
        where_clause = f"""
original_movein_date >= %({window_start_param})s
  AND original_movein_date <= %({window_end_param})s
  AND movein_date IS NOT NULL
  AND movein_date <= %({window_end_param})s
  AND COALESCE(move_renew_flag, 0) = 0
""".strip()
        return _build_metric_sql(
            where_clause=where_clause,
            result_select_sql="""
SELECT
    tenant_type,
    COUNT(DISTINCT room_key) AS cnt
FROM deduplicated_filtered_contracts
WHERE rn = 1
GROUP BY tenant_type
""".strip(),
        )

    def split_planned_moveins(window_end_param: str) -> str:
        where_clause = f"""
{movein_prediction_date_column} > %(snapshot_asof)s
  AND {movein_prediction_date_column} <= %({window_end_param})s
  AND COALESCE(move_renew_flag, 0) = 0
  AND management_status_code IN {PLANNED_MOVEIN_STATUSES}
""".strip()
        return _build_metric_sql(
            where_clause=where_clause,
            result_select_sql="""
SELECT
    tenant_type,
    COUNT(DISTINCT room_key) AS cnt
FROM deduplicated_filtered_contracts
WHERE rn = 1
GROUP BY tenant_type
""".strip(),
        )

    def split_completed_moveouts(window_start_param: str, window_end_param: str) -> str:
        where_clause = f"""
moveout_date >= %({window_start_param})s
  AND moveout_date <= %({window_end_param})s
  AND management_status_code IN {COMPLETED_MOVEOUT_STATUSES}
""".strip()
        return _build_metric_sql(
            where_clause=where_clause,
            result_select_sql="""
SELECT
    tenant_type,
    COUNT(DISTINCT room_key) AS cnt
FROM deduplicated_filtered_contracts
WHERE rn = 1
GROUP BY tenant_type
""".strip(),
        )

    def split_planned_moveouts(window_end_param: str) -> str:
        where_clause = f"""
{moveout_prediction_date_column} > %(snapshot_asof)s
  AND {moveout_prediction_date_column} <= %({window_end_param})s
  AND management_status_code IN {PLANNED_MOVEOUT_STATUSES}
""".strip()
        return _build_metric_sql(
            where_clause=where_clause,
            result_select_sql="""
SELECT
    tenant_type,
    COUNT(DISTINCT room_key) AS cnt
FROM deduplicated_filtered_contracts
WHERE rn = 1
GROUP BY tenant_type
""".strip(),
        )

    d5_sql = _build_d5_fact_aligned_sql()

    return {
        "d5_occupied_rooms": QuerySpec(
            metric_id="d5_occupied_rooms",
            sql=d5_sql,
            source_layer="staging",
            result_mode="scalar",
            value_column="occupied_rooms",
            query_tag="metric:d5:fact_aligned",
        ),
        "feb_completed_moveins": QuerySpec(
            metric_id="feb_completed_moveins",
            sql=split_moveins("feb_start", "snapshot_asof", COMPLETED_MOVEIN_STATUSES),
            source_layer="staging",
            result_mode="split",
            value_column="cnt",
            query_tag="metric:feb_completed_moveins",
        ),
        "feb_planned_moveins": QuerySpec(
            metric_id="feb_planned_moveins",
            sql=split_planned_moveins("feb_end"),
            source_layer="staging",
            result_mode="split",
            value_column="cnt",
            query_tag=f"metric:feb_planned_moveins:{movein_prediction_date_column}",
        ),
        "feb_completed_moveouts": QuerySpec(
            metric_id="feb_completed_moveouts",
            sql=split_completed_moveouts("feb_start", "snapshot_asof"),
            source_layer="staging",
            result_mode="split",
            value_column="cnt",
            query_tag="metric:feb_completed_moveouts",
        ),
        "feb_planned_moveouts": QuerySpec(
            metric_id="feb_planned_moveouts",
            sql=split_planned_moveouts("feb_end"),
            source_layer="staging",
            result_mode="split",
            value_column="cnt",
            query_tag=f"metric:feb_planned_moveouts:{moveout_prediction_date_column}",
        ),
        "mar_completed_moveins": QuerySpec(
            metric_id="mar_completed_moveins",
            sql=split_moveins("mar_start", "snapshot_asof", COMPLETED_MOVEIN_STATUSES),
            source_layer="staging",
            result_mode="split",
            value_column="cnt",
            query_tag="metric:mar_completed_moveins",
        ),
        "mar_planned_moveins": QuerySpec(
            metric_id="mar_planned_moveins",
            sql=split_planned_moveins("mar_end"),
            source_layer="staging",
            result_mode="split",
            value_column="cnt",
            query_tag=f"metric:mar_planned_moveins:{movein_prediction_date_column}",
        ),
        "mar_planned_moveouts": QuerySpec(
            metric_id="mar_planned_moveouts",
            sql=split_planned_moveouts("mar_end"),
            source_layer="staging",
            result_mode="split",
            value_column="cnt",
            query_tag=f"metric:mar_planned_moveouts:{moveout_prediction_date_column}",
        ),
    }
