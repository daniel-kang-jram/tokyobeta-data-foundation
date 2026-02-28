from __future__ import annotations

from datetime import date, datetime, time
from typing import Dict

from scripts.flash_report_fill.types import QuerySpec


CORPORATE_CODES = (2, 3)
INDIVIDUAL_CODES = (1, 6, 7, 9)

ACTIVE_OCCUPANCY_STATUSES = (7, 9, 10, 11, 12, 13, 14, 15)
PLANNED_MOVEIN_STATUSES = (4, 5, 6, 11, 12)
COMPLETED_MOVEIN_STATUSES = (6, 7, 9, 10, 11, 12, 13, 14, 15, 16, 17)
COMPLETED_MOVEOUT_STATUSES = (16, 17)
PLANNED_MOVEOUT_STATUSES = (14, 15)

TENANT_TYPE_CASE = """
CASE
    WHEN c.moving_agreement_type IN (2, 3) THEN 'corporate'
    WHEN c.moving_agreement_type IN (1, 6, 7, 9) THEN 'individual'
    ELSE 'unknown'
END
""".strip()

BASE_CONTRACTS_CTE = """
WITH deduplicated_contracts AS (
    SELECT
        m.id AS moving_id,
        m.tenant_id,
        m.apartment_id,
        m.room_id,
        m.movein_date,
        m.moveout_date,
        m.moveout_plans_date,
        m.moveout_date_integrated,
        m.moving_agreement_type,
        COALESCE(m.cancel_flag, 0) AS cancel_flag,
        t.status AS management_status_code,
        ROW_NUMBER() OVER (
            PARTITION BY m.tenant_id, m.apartment_id, m.room_id
            ORDER BY m.movein_date DESC, m.updated_at DESC, m.id DESC
        ) AS rn
    FROM staging.movings m
    INNER JOIN staging.tenants t
        ON m.tenant_id = t.id
    WHERE COALESCE(m.cancel_flag, 0) = 0
),
contracts AS (
    SELECT
        d.*,
        CONCAT(d.apartment_id, '-', d.room_id) AS room_key,
        COALESCE(d.moveout_plans_date, d.moveout_date) AS effective_moveout_at
    FROM deduplicated_contracts d
    WHERE d.rn = 1
),
classified AS (
    SELECT
        c.*,
        {tenant_type_case} AS tenant_type
    FROM contracts c
)
""".strip().format(tenant_type_case=TENANT_TYPE_CASE)


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


def build_metric_queries() -> Dict[str, QuerySpec]:
    """Build decision-complete SQL specs for all flash report metrics."""
    d5_sql = f"""
{BASE_CONTRACTS_CTE}
SELECT
    COUNT(DISTINCT room_key) AS occupied_rooms
FROM classified
WHERE CAST(movein_date AS DATETIME) <= %(snapshot_start)s
  AND (
      effective_moveout_at IS NULL
      OR CAST(effective_moveout_at AS DATETIME) > %(snapshot_start)s
  )
  AND management_status_code IN {ACTIVE_OCCUPANCY_STATUSES}
""".strip()

    def split_moveins(window_start_param: str, window_end_param: str, status_tuple: tuple[int, ...]) -> str:
        return f"""
{BASE_CONTRACTS_CTE}
SELECT
    tenant_type,
    COUNT(DISTINCT room_key) AS cnt
FROM classified
WHERE movein_date >= %({window_start_param})s
  AND movein_date <= %({window_end_param})s
  AND management_status_code IN {status_tuple}
GROUP BY tenant_type
""".strip()

    def split_planned_moveins(window_end_param: str) -> str:
        return f"""
{BASE_CONTRACTS_CTE}
SELECT
    tenant_type,
    COUNT(DISTINCT room_key) AS cnt
FROM classified
WHERE movein_date > %(snapshot_asof)s
  AND movein_date <= %({window_end_param})s
  AND management_status_code IN {PLANNED_MOVEIN_STATUSES}
GROUP BY tenant_type
""".strip()

    def split_completed_moveouts(window_start_param: str, window_end_param: str) -> str:
        return f"""
{BASE_CONTRACTS_CTE}
SELECT
    tenant_type,
    COUNT(DISTINCT room_key) AS cnt
FROM classified
WHERE moveout_plans_date >= %({window_start_param})s
  AND moveout_plans_date <= %({window_end_param})s
  AND management_status_code IN {COMPLETED_MOVEOUT_STATUSES}
GROUP BY tenant_type
""".strip()

    def split_planned_moveouts(window_end_param: str) -> str:
        return f"""
{BASE_CONTRACTS_CTE}
SELECT
    tenant_type,
    COUNT(DISTINCT room_key) AS cnt
FROM classified
WHERE moveout_date > %(snapshot_asof)s
  AND moveout_date <= %({window_end_param})s
  AND management_status_code IN {PLANNED_MOVEOUT_STATUSES}
GROUP BY tenant_type
""".strip()

    return {
        "d5_occupied_rooms": QuerySpec(
            metric_id="d5_occupied_rooms",
            sql=d5_sql,
            source_layer="staging",
            result_mode="scalar",
            value_column="occupied_rooms",
            query_tag="metric:d5",
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
            query_tag="metric:feb_planned_moveins",
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
            query_tag="metric:feb_planned_moveouts",
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
            query_tag="metric:mar_planned_moveins",
        ),
        "mar_planned_moveouts": QuerySpec(
            metric_id="mar_planned_moveouts",
            sql=split_planned_moveouts("mar_end"),
            source_layer="staging",
            result_mode="split",
            value_column="cnt",
            query_tag="metric:mar_planned_moveouts",
        ),
    }
