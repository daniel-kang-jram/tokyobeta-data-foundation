from __future__ import annotations

from datetime import date
from typing import Dict, Iterable, List, Tuple

from scripts.flash_report_fill.sql import (
    ACTIVE_OCCUPANCY_STATUSES,
    DEFAULT_MOVEIN_PREDICTION_COLUMN,
    PLANNED_MOVEIN_STATUSES,
    SUPPORTED_MOVEIN_PREDICTION_COLUMNS,
    build_metric_queries,
)
from scripts.flash_report_fill.types import FlashReportQueryConfig, MetricRecord, ReconciliationRecord, WarningRecord


def metrics_records_to_csv_rows(records: Iterable[MetricRecord]) -> List[Dict[str, object]]:
    """Convert metric records to CSV-friendly dictionaries."""
    rows: List[Dict[str, object]] = []
    for record in records:
        rows.append(
            {
                "metric_id": record.metric_id,
                "sheet": record.sheet,
                "cell": record.cell,
                "value": record.value,
                "month": record.month,
                "tenant_type": record.tenant_type,
                "window_start": record.window_start,
                "window_end": record.window_end,
                "asof_ts_jst": record.asof_ts_jst,
                "source_layer": record.source_layer,
                "query_tag": record.query_tag,
                "query_sql": record.query_sql,
            }
        )
    return rows


def reconciliation_records_to_csv_rows(
    records: Iterable[ReconciliationRecord],
) -> List[Dict[str, object]]:
    """Convert reconciliation records to CSV-friendly dictionaries."""
    rows: List[Dict[str, object]] = []
    for record in records:
        rows.append(
            {
                "reconciliation_id": record.reconciliation_id,
                "expected_value": record.expected_value,
                "reference_value": record.reference_value,
                "delta": record.delta,
                "reference_source": record.reference_source,
                "note": record.note,
                "asof_date": record.asof_date,
            }
        )
    return rows


def build_reconciliation_records(
    cursor,
    cell_values: Dict[str, int],
    snapshot_start_date: date,
    snapshot_asof_date: date,
    feb_start_date: date,
    feb_end_date: date,
    mar_start_date: date,
    mar_end_date: date,
    reconciliation_asof_date: date,
    mar_planned_movein_cells: List[str],
    movein_prediction_date_column: str = DEFAULT_MOVEIN_PREDICTION_COLUMN,
) -> List[ReconciliationRecord]:
    """Build staging-vs-silver-vs-gold reconciliation rows."""
    prediction_column = _validate_movein_prediction_date_column(movein_prediction_date_column)
    records: List[ReconciliationRecord] = []

    expected_d5 = int(cell_values.get("D5", 0))
    silver_occupied = _silver_occupied_rooms(cursor, snapshot_start_date)
    records.append(
        ReconciliationRecord(
            reconciliation_id="silver_occupied_rooms",
            expected_value=expected_d5,
            reference_value=silver_occupied,
            delta=expected_d5 - silver_occupied,
            reference_source="silver.tenant_room_snapshot_daily",
            note="Compared D5 against silver snapshot at snapshot_start date.",
            asof_date=str(snapshot_start_date),
        )
    )

    expected_mar_planned_moveins = sum(int(cell_values.get(cell, 0)) for cell in mar_planned_movein_cells)
    silver_mar_planned_split = _silver_asof_mar_planned_moveins_split(
        cursor=cursor,
        snapshot_date=reconciliation_asof_date,
        asof_date=reconciliation_asof_date,
        mar_end_date=mar_end_date,
        movein_prediction_date_column=prediction_column,
    )
    silver_mar_planned_total = (
        silver_mar_planned_split["individual"] + silver_mar_planned_split["corporate"]
    )
    records.append(
        ReconciliationRecord(
            reconciliation_id="silver_asof_mar_planned_moveins_total",
            expected_value=expected_mar_planned_moveins,
            reference_value=silver_mar_planned_total,
            delta=expected_mar_planned_moveins - silver_mar_planned_total,
            reference_source="silver.tenant_room_snapshot_daily",
            note=(
                "Compared March planned move-ins from Excel cells against silver snapshot-anchored "
                f"counts using {prediction_column}."
            ),
            asof_date=str(reconciliation_asof_date),
        )
    )
    records.append(
        ReconciliationRecord(
            reconciliation_id="silver_asof_mar_planned_moveins_individual",
            expected_value=int(cell_values.get(mar_planned_movein_cells[0], 0)),
            reference_value=silver_mar_planned_split["individual"],
            delta=int(cell_values.get(mar_planned_movein_cells[0], 0))
            - silver_mar_planned_split["individual"],
            reference_source="silver.tenant_room_snapshot_daily",
            note="Individual split for March planned move-ins at silver as-of snapshot.",
            asof_date=str(reconciliation_asof_date),
        )
    )
    records.append(
        ReconciliationRecord(
            reconciliation_id="silver_asof_mar_planned_moveins_corporate",
            expected_value=int(cell_values.get(mar_planned_movein_cells[1], 0)),
            reference_value=silver_mar_planned_split["corporate"],
            delta=int(cell_values.get(mar_planned_movein_cells[1], 0))
            - silver_mar_planned_split["corporate"],
            reference_source="silver.tenant_room_snapshot_daily",
            note="Corporate split for March planned move-ins at silver as-of snapshot.",
            asof_date=str(reconciliation_asof_date),
        )
    )

    feb_our_moveins = int(
        cell_values.get("D11", 0)
        + cell_values.get("E11", 0)
        + cell_values.get("D12", 0)
        + cell_values.get("E12", 0)
    )
    feb_our_moveouts = int(
        cell_values.get("D15", 0)
        + cell_values.get("E15", 0)
        + cell_values.get("D16", 0)
        + cell_values.get("E16", 0)
    )
    mar_our_moveins = int(
        cell_values.get("D13", 0)
        + cell_values.get("E13", 0)
        + cell_values.get("D14", 0)
        + cell_values.get("E14", 0)
    )
    mar_our_moveouts = int(cell_values.get("D17", 0) + cell_values.get("E17", 0))

    feb_gold = _gold_month_totals(cursor, feb_start_date, feb_end_date)
    mar_gold = _gold_month_totals(cursor, mar_start_date, mar_end_date)

    records.append(
        ReconciliationRecord(
            reconciliation_id="gold_feb_moveins_total",
            expected_value=feb_our_moveins,
            reference_value=feb_gold["moveins"],
            delta=feb_our_moveins - feb_gold["moveins"],
            reference_source="gold.occupancy_daily_metrics",
            note="Guideline-first logic differs from KPI semantics; non-zero delta can be expected.",
            asof_date=str(snapshot_asof_date),
        )
    )
    records.append(
        ReconciliationRecord(
            reconciliation_id="gold_feb_moveouts_total",
            expected_value=feb_our_moveouts,
            reference_value=feb_gold["moveouts"],
            delta=feb_our_moveouts - feb_gold["moveouts"],
            reference_source="gold.occupancy_daily_metrics",
            note="Guideline-first logic differs from KPI semantics; non-zero delta can be expected.",
            asof_date=str(snapshot_asof_date),
        )
    )
    records.append(
        ReconciliationRecord(
            reconciliation_id="gold_mar_moveins_total",
            expected_value=mar_our_moveins,
            reference_value=mar_gold["moveins"],
            delta=mar_our_moveins - mar_gold["moveins"],
            reference_source="gold.occupancy_daily_metrics",
            note="Guideline-first logic differs from KPI semantics; non-zero delta can be expected.",
            asof_date=str(snapshot_asof_date),
        )
    )
    records.append(
        ReconciliationRecord(
            reconciliation_id="gold_mar_moveouts_total",
            expected_value=mar_our_moveouts,
            reference_value=mar_gold["moveouts"],
            delta=mar_our_moveouts - mar_gold["moveouts"],
            reference_source="gold.occupancy_daily_metrics",
            note="Guideline-first logic differs from KPI semantics; non-zero delta can be expected.",
            asof_date=str(snapshot_asof_date),
        )
    )

    return records


def build_d5_discrepancy_records(
    cursor,
    snapshot_start_ts: str,
    snapshot_start_date: date,
    benchmark_value: int = 11271,
    tolerance: int = 10,
) -> Tuple[List[ReconciliationRecord], List[WarningRecord]]:
    """Build D5 fact-aligned diagnostics and tolerance warnings."""
    fact_aligned_count = _query_d5_fact_aligned_count(cursor, snapshot_start_ts)
    categories = _query_d5_discrepancy_categories(cursor, snapshot_start_ts)

    fact_aligned_delta = fact_aligned_count - benchmark_value

    records = [
        ReconciliationRecord(
            reconciliation_id="d5_fact_aligned_vs_benchmark",
            expected_value=benchmark_value,
            reference_value=fact_aligned_count,
            delta=fact_aligned_delta,
            reference_source="staging.movings+staging.tenants",
            note="Fact-aligned occupancy using is_moveout=0 and room-priority dedupe.",
            asof_date=str(snapshot_start_date),
        ),
        ReconciliationRecord(
            reconciliation_id="d5_discrepancy_status7_midnight_adjusted_rooms",
            expected_value=0,
            reference_value=categories["status7_midnight_adjusted_rooms"],
            delta=categories["status7_midnight_adjusted_rooms"],
            reference_source="staging.movings+staging.tenants",
            note="Rooms adjusted out by status=7 midnight correction in fact-aligned mode.",
            asof_date=str(snapshot_start_date),
        ),
        ReconciliationRecord(
            reconciliation_id="d5_discrepancy_fact_multi_tenant_collision_rooms",
            expected_value=0,
            reference_value=categories["fact_multi_tenant_collision_rooms"],
            delta=categories["fact_multi_tenant_collision_rooms"],
            reference_source="staging.movings+staging.tenants",
            note="Physical rooms with multiple fact-aligned candidates before room-priority selection.",
            asof_date=str(snapshot_start_date),
        ),
    ]

    warnings: List[WarningRecord] = []
    if abs(fact_aligned_delta) > tolerance:
        warnings.append(
            WarningRecord(
                code="WARN_D5_FACT_ALIGNED_BENCHMARK_DELTA",
                message="D5 fact-aligned result differs from benchmark beyond tolerance.",
                count=abs(fact_aligned_delta),
            )
        )

    return records, warnings


def _silver_occupied_rooms(cursor, snapshot_date: date) -> int:
    try:
        cursor.execute(
            """
            SELECT COUNT(DISTINCT CONCAT(apartment_id, '-', room_id)) AS occupied_rooms
            FROM silver.tenant_room_snapshot_daily
            WHERE snapshot_date = %s
              AND is_room_primary = TRUE
            """,
            (snapshot_date,),
        )
    except Exception as exc:
        # Compatibility fallback for environments where is_room_primary is absent.
        if not _is_missing_is_room_primary_error(exc):
            raise
        cursor.execute(
            """
            SELECT COUNT(DISTINCT CONCAT(apartment_id, '-', room_id)) AS occupied_rooms
            FROM silver.tenant_room_snapshot_daily
            WHERE snapshot_date = %s
            """,
            (snapshot_date,),
        )
    row = cursor.fetchone()
    value = row["occupied_rooms"] if isinstance(row, dict) else row[0]
    return int(value or 0)


def _is_missing_is_room_primary_error(exc: Exception) -> bool:
    args = getattr(exc, "args", ())
    if not args:
        return False
    code = args[0]
    if code != 1054:
        return False
    message = str(args[1]) if len(args) > 1 else str(exc)
    return "is_room_primary" in message


def _gold_month_totals(cursor, month_start: date, month_end: date) -> Dict[str, int]:
    cursor.execute(
        """
        SELECT
            COALESCE(SUM(new_moveins), 0) AS moveins,
            COALESCE(SUM(new_moveouts), 0) AS moveouts
        FROM gold.occupancy_daily_metrics
        WHERE snapshot_date BETWEEN %s AND %s
        """,
        (month_start, month_end),
    )
    row = cursor.fetchone()
    if isinstance(row, dict):
        return {"moveins": int(row["moveins"] or 0), "moveouts": int(row["moveouts"] or 0)}
    return {"moveins": int(row[0] or 0), "moveouts": int(row[1] or 0)}


def _silver_asof_mar_planned_moveins_split(
    cursor,
    snapshot_date: date,
    asof_date: date,
    mar_end_date: date,
    movein_prediction_date_column: str,
) -> Dict[str, int]:
    prediction_column = _validate_movein_prediction_date_column(movein_prediction_date_column)
    cursor.execute(
        f"""
/* silver_asof_mar_planned_moveins_split */
SELECT
    CASE
        WHEN m.moving_agreement_type IN (2, 3) THEN 'corporate'
        WHEN m.moving_agreement_type IN (1, 6, 7, 9) THEN 'individual'
        ELSE 'unknown'
    END AS tenant_type,
    COUNT(DISTINCT CONCAT(s.apartment_id, '-', s.room_id)) AS cnt
FROM silver.tenant_room_snapshot_daily s
INNER JOIN staging.movings m
    ON s.moving_id = m.id
WHERE s.snapshot_date = %s
  AND COALESCE(m.cancel_flag, 0) = 0
  AND COALESCE(m.move_renew_flag, 0) = 0
  AND s.management_status_code IN {PLANNED_MOVEIN_STATUSES}
  AND m.{prediction_column} > %s
  AND m.{prediction_column} <= %s
GROUP BY tenant_type
""",
        (snapshot_date, asof_date, mar_end_date),
    )
    rows = cursor.fetchall() or []
    split = {"individual": 0, "corporate": 0, "unknown": 0}
    for row in rows:
        tenant_type = str(row.get("tenant_type", "unknown"))
        split[tenant_type] = int(row.get("cnt", 0) or 0)
    return split


def _validate_movein_prediction_date_column(column: str) -> str:
    if column not in SUPPORTED_MOVEIN_PREDICTION_COLUMNS:
        allowed = ", ".join(SUPPORTED_MOVEIN_PREDICTION_COLUMNS)
        raise ValueError(f"Unsupported move-in prediction column: {column}. Allowed: {allowed}")
    return column


D5_DISCREPANCY_BASE_CTE = """
WITH base AS (
    SELECT
        m.id AS moving_id,
        m.tenant_id,
        m.apartment_id,
        m.room_id,
        m.movein_date,
        m.moveout_date,
        m.moveout_plans_date,
        m.updated_at,
        COALESCE(m.cancel_flag, 0) AS cancel_flag,
        COALESCE(m.is_moveout, 0) AS is_moveout,
        t.status AS management_status_code,
        CONCAT(m.apartment_id, '-', m.room_id) AS room_key
    FROM staging.movings m
    INNER JOIN staging.tenants t
        ON m.tenant_id = t.id
    WHERE COALESCE(m.cancel_flag, 0) = 0
),
fact_filtered AS (
    SELECT
        b.*,
        CONCAT(b.apartment_id, '-', b.room_id) AS fact_room_key
    FROM base b
    WHERE b.management_status_code IN {active_statuses}
      AND b.is_moveout = 0
      AND (
          b.management_status_code <> 7
          OR b.movein_date < %(snapshot_start_ts)s
      )
),
fact_dedup_tenant_room AS (
    SELECT
        f.*,
        ROW_NUMBER() OVER (
            PARTITION BY f.tenant_id, f.apartment_id, f.room_id
            ORDER BY f.movein_date DESC, f.updated_at DESC, f.moving_id DESC
        ) AS fact_rn_tenant_room
    FROM fact_filtered f
),
fact_candidates AS (
    SELECT *
    FROM fact_dedup_tenant_room
    WHERE fact_rn_tenant_room = 1
),
fact_room_priority AS (
    SELECT
        f.*,
        ROW_NUMBER() OVER (
            PARTITION BY apartment_id, room_id
            ORDER BY
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
                END,
                movein_date DESC,
                updated_at DESC,
                moving_id DESC
        ) AS rn_room
    FROM fact_candidates f
),
fact_rooms AS (
    SELECT room_key, apartment_id, room_id
    FROM fact_room_priority
    WHERE rn_room = 1
)
""".strip().format(active_statuses=ACTIVE_OCCUPANCY_STATUSES)

def _query_d5_fact_aligned_count(cursor, snapshot_start_ts: str) -> int:
    fact_aligned_query = build_metric_queries(FlashReportQueryConfig())["d5_occupied_rooms"].sql
    fact_aligned_query = fact_aligned_query.replace("AS occupied_rooms", "AS d5_fact_aligned_count", 1)
    cursor.execute(
        """
/* d5_fact_aligned_count */
"""
        + fact_aligned_query,
        {"snapshot_start": snapshot_start_ts},
    )
    row = cursor.fetchone() or {}
    return int(row.get("d5_fact_aligned_count", 0))


def _query_d5_discrepancy_categories(cursor, snapshot_start_ts: str) -> Dict[str, int]:
    cursor.execute(
        f"""
/* d5_discrepancy_categories */
{D5_DISCREPANCY_BASE_CTE},
status7_midnight_excluded AS (
    SELECT COUNT(DISTINCT CONCAT(apartment_id, '-', room_id)) AS room_count
    FROM base
    WHERE is_moveout = 0
      AND management_status_code = 7
      AND movein_date >= %(snapshot_start_ts)s
),
multi_tenant_collisions AS (
    SELECT COUNT(*) AS room_count
    FROM (
        SELECT apartment_id, room_id
        FROM fact_candidates
        GROUP BY apartment_id, room_id
        HAVING COUNT(*) >= 2
    ) c
)
SELECT
    (SELECT room_count FROM status7_midnight_excluded) AS status7_midnight_adjusted_rooms,
    (SELECT room_count FROM multi_tenant_collisions) AS fact_multi_tenant_collision_rooms
""",
        {"snapshot_start_ts": snapshot_start_ts},
    )
    row = cursor.fetchone() or {}
    return {
        "status7_midnight_adjusted_rooms": int(row.get("status7_midnight_adjusted_rooms", 0) or 0),
        "fact_multi_tenant_collision_rooms": int(row.get("fact_multi_tenant_collision_rooms", 0) or 0),
    }
