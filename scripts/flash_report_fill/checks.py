from __future__ import annotations

from typing import Dict, List, Tuple

from scripts.flash_report_fill.sql import ACTIVE_OCCUPANCY_STATUSES, BASE_CONTRACTS_CTE
from scripts.flash_report_fill.types import WarningRecord


def run_anomaly_checks(cursor, params: Dict[str, object], limit: int = 200) -> Tuple[Dict[str, List[Dict[str, object]]], List[WarningRecord]]:
    """Run checks A/B/C and return rows plus warning summary."""
    checks = {
        "double_active_rooms": _fetch_rows(cursor, build_double_active_rooms_sql(limit), params),
        "tenant_switch_gaps": _fetch_rows(cursor, build_tenant_switch_gap_sql(limit), params),
        "same_tenant_multi_status": _fetch_rows(cursor, build_same_tenant_multi_status_sql(limit), params),
    }

    warnings: List[WarningRecord] = []
    for name, rows in checks.items():
        if rows:
            warnings.append(
                WarningRecord(
                    code=f"WARN_{name.upper()}",
                    message=f"{name} check returned flagged rows.",
                    count=len(rows),
                )
            )
    return checks, warnings


def build_double_active_rooms_sql(limit: int) -> str:
    return f"""
{BASE_CONTRACTS_CTE}
SELECT
    apartment_id,
    room_id,
    COUNT(DISTINCT tenant_id) AS active_count,
    GROUP_CONCAT(DISTINCT tenant_id ORDER BY tenant_id) AS tenant_ids
FROM classified
WHERE CAST(movein_date AS DATETIME) <= %(snapshot_asof)s
  AND (
      effective_moveout_at IS NULL
      OR CAST(effective_moveout_at AS DATETIME) > %(snapshot_asof)s
  )
  AND management_status_code IN {ACTIVE_OCCUPANCY_STATUSES}
GROUP BY apartment_id, room_id
HAVING COUNT(DISTINCT tenant_id) >= 2
ORDER BY active_count DESC, apartment_id, room_id
LIMIT {int(limit)}
""".strip()


def build_tenant_switch_gap_sql(limit: int, suspicious_gap_days: int = 45) -> str:
    return f"""
{BASE_CONTRACTS_CTE},
ordered AS (
    SELECT
        apartment_id,
        room_id,
        tenant_id,
        movein_date,
        COALESCE(moveout_plans_date, moveout_date) AS effective_moveout_at,
        LEAD(tenant_id) OVER (
            PARTITION BY apartment_id, room_id
            ORDER BY movein_date, moving_id
        ) AS next_tenant_id,
        LEAD(movein_date) OVER (
            PARTITION BY apartment_id, room_id
            ORDER BY movein_date, moving_id
        ) AS next_movein_date
    FROM classified
)
SELECT
    apartment_id,
    room_id,
    tenant_id,
    next_tenant_id,
    movein_date,
    effective_moveout_at,
    next_movein_date,
    DATEDIFF(next_movein_date, effective_moveout_at) AS gap_days,
    CASE
        WHEN next_movein_date IS NOT NULL AND effective_moveout_at IS NOT NULL
             AND next_movein_date < effective_moveout_at THEN 'overlap'
        WHEN next_movein_date IS NOT NULL AND effective_moveout_at IS NOT NULL
             AND DATEDIFF(next_movein_date, effective_moveout_at) > {int(suspicious_gap_days)} THEN 'large_gap'
        WHEN next_movein_date IS NOT NULL AND effective_moveout_at IS NULL THEN 'unknown_gap'
        ELSE NULL
    END AS issue_type
FROM ordered
WHERE next_tenant_id IS NOT NULL
  AND (
      (next_movein_date IS NOT NULL AND effective_moveout_at IS NOT NULL AND next_movein_date < effective_moveout_at)
      OR (next_movein_date IS NOT NULL AND effective_moveout_at IS NOT NULL AND DATEDIFF(next_movein_date, effective_moveout_at) > {int(suspicious_gap_days)})
      OR (next_movein_date IS NOT NULL AND effective_moveout_at IS NULL)
  )
ORDER BY apartment_id, room_id, movein_date
LIMIT {int(limit)}
""".strip()


def build_same_tenant_multi_status_sql(limit: int) -> str:
    return f"""
WITH asof_snapshot AS (
    SELECT MAX(snapshot_date) AS snapshot_date
    FROM silver.tenant_room_snapshot_daily
    WHERE snapshot_date <= DATE(%(snapshot_asof)s)
)
SELECT
    s.snapshot_date,
    s.tenant_id,
    s.apartment_id,
    s.room_id,
    COUNT(*) AS row_count,
    COUNT(DISTINCT s.management_status_code) AS status_variants,
    GROUP_CONCAT(DISTINCT s.management_status_code ORDER BY s.management_status_code) AS status_codes
FROM silver.tenant_room_snapshot_daily s
INNER JOIN asof_snapshot a
    ON s.snapshot_date = a.snapshot_date
GROUP BY s.snapshot_date, s.tenant_id, s.apartment_id, s.room_id
HAVING COUNT(*) > 1 OR COUNT(DISTINCT s.management_status_code) > 1
ORDER BY row_count DESC, status_variants DESC, s.tenant_id
LIMIT {int(limit)}
""".strip()


def _fetch_rows(cursor, sql: str, params: Dict[str, object]) -> List[Dict[str, object]]:
    cursor.execute(sql, params)
    rows = cursor.fetchall()
    if rows is None:
        return []
    return list(rows)
