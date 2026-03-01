from __future__ import annotations

from datetime import date
from typing import Dict, Iterable, List, Tuple

from scripts.flash_report_fill.sql import (
    ACTIVE_OCCUPANCY_STATUSES,
    D5_MODE_FACT_ALIGNED,
    D5_MODE_STRICT,
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
) -> List[ReconciliationRecord]:
    """Build staging-vs-silver-vs-gold reconciliation rows."""
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
    """Build deterministic D5 discrepancy diagnostics and tolerance warnings."""
    strict_count = _query_d5_strict_count(cursor, snapshot_start_ts)
    fact_aligned_count = _query_d5_fact_aligned_count(cursor, snapshot_start_ts)
    categories = _query_d5_discrepancy_categories(cursor, snapshot_start_ts)

    strict_delta = strict_count - benchmark_value
    fact_aligned_delta = fact_aligned_count - benchmark_value
    fact_minus_strict_delta = fact_aligned_count - strict_count

    records = [
        ReconciliationRecord(
            reconciliation_id="d5_strict_vs_benchmark",
            expected_value=benchmark_value,
            reference_value=strict_count,
            delta=strict_delta,
            reference_source="staging.movings+staging.tenants",
            note="Strict point-in-time occupancy with active status filter.",
            asof_date=str(snapshot_start_date),
        ),
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
            reconciliation_id="d5_fact_aligned_minus_strict",
            expected_value=0,
            reference_value=fact_minus_strict_delta,
            delta=fact_minus_strict_delta,
            reference_source="staging.movings+staging.tenants",
            note=(
                "Net difference between fact-aligned and strict occupancy logic "
                "(status/room-priority operational view minus strict point-in-time date gating)."
            ),
            asof_date=str(snapshot_start_date),
        ),
        ReconciliationRecord(
            reconciliation_id="d5_discrepancy_excluded_by_strict_gating",
            expected_value=0,
            reference_value=categories["excluded_by_strict_gating"],
            delta=categories["excluded_by_strict_gating"],
            reference_source="staging.movings+staging.tenants",
            note="Rooms included by fact-aligned logic but excluded by strict date gating.",
            asof_date=str(snapshot_start_date),
        ),
        ReconciliationRecord(
            reconciliation_id="d5_discrepancy_excluded_by_status7_midnight",
            expected_value=0,
            reference_value=categories["excluded_by_status7_midnight"],
            delta=categories["excluded_by_status7_midnight"],
            reference_source="staging.movings+staging.tenants",
            note="Rooms removed by status=7 midnight correction.",
            asof_date=str(snapshot_start_date),
        ),
        ReconciliationRecord(
            reconciliation_id="d5_discrepancy_multi_tenant_collision_rooms",
            expected_value=0,
            reference_value=categories["multi_tenant_collision_rooms"],
            delta=categories["multi_tenant_collision_rooms"],
            reference_source="staging.movings+staging.tenants",
            note="Physical rooms with multiple fact candidates before room-priority selection.",
            asof_date=str(snapshot_start_date),
        ),
    ]

    warnings: List[WarningRecord] = []
    if abs(strict_delta) > tolerance or abs(fact_aligned_delta) > tolerance:
        warnings.append(
            WarningRecord(
                code="WARN_D5_BENCHMARK_DELTA",
                message="D5 strict and fact-aligned results differ from benchmark beyond tolerance.",
                count=max(abs(strict_delta), abs(fact_aligned_delta)),
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
    except Exception:
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
strict_filtered AS (
    SELECT
        b.*,
        COALESCE(b.moveout_plans_date, b.moveout_date) AS effective_moveout_at,
        CONCAT(b.apartment_id, '-', b.room_id) AS strict_room_key
    FROM base b
    WHERE b.management_status_code IN {active_statuses}
      AND CAST(b.movein_date AS DATETIME) <= %(snapshot_start_ts)s
      AND (
          COALESCE(b.moveout_plans_date, b.moveout_date) IS NULL
          OR CAST(COALESCE(b.moveout_plans_date, b.moveout_date) AS DATETIME) > %(snapshot_start_ts)s
      )
),
strict_dedup_tenant_room AS (
    SELECT
        s.*,
        ROW_NUMBER() OVER (
            PARTITION BY s.tenant_id, s.apartment_id, s.room_id
            ORDER BY s.movein_date DESC, s.updated_at DESC, s.moving_id DESC
        ) AS strict_rn_tenant_room
    FROM strict_filtered s
),
strict_latest_tenant_room AS (
    SELECT *
    FROM strict_dedup_tenant_room
    WHERE strict_rn_tenant_room = 1
),
strict_rooms AS (
    SELECT DISTINCT strict_room_key AS room_key, apartment_id, room_id
    FROM strict_latest_tenant_room
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


def _query_d5_strict_count(cursor, snapshot_start_ts: str) -> int:
    strict_query = build_metric_queries(
        FlashReportQueryConfig(d5_mode=D5_MODE_STRICT)
    )["d5_occupied_rooms"].sql
    strict_query = strict_query.replace("AS occupied_rooms", "AS d5_strict_count", 1)
    cursor.execute(
        """
/* d5_strict_count */
"""
        + strict_query,
        {"snapshot_start": snapshot_start_ts},
    )
    row = cursor.fetchone() or {}
    return int(row.get("d5_strict_count", 0))


def _query_d5_fact_aligned_count(cursor, snapshot_start_ts: str) -> int:
    fact_aligned_query = build_metric_queries(
        FlashReportQueryConfig(d5_mode=D5_MODE_FACT_ALIGNED)
    )["d5_occupied_rooms"].sql
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
strict_excluded AS (
    SELECT f.room_key
    FROM fact_rooms f
    LEFT JOIN strict_rooms s
        ON f.room_key = s.room_key
    WHERE s.room_key IS NULL
),
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
    (SELECT COUNT(*) FROM strict_excluded) AS excluded_by_strict_gating,
    (SELECT room_count FROM status7_midnight_excluded) AS excluded_by_status7_midnight,
    (SELECT room_count FROM multi_tenant_collisions) AS multi_tenant_collision_rooms
""",
        {"snapshot_start_ts": snapshot_start_ts},
    )
    row = cursor.fetchone() or {}
    return {
        "excluded_by_strict_gating": int(row.get("excluded_by_strict_gating", 0) or 0),
        "excluded_by_status7_midnight": int(row.get("excluded_by_status7_midnight", 0) or 0),
        "multi_tenant_collision_rooms": int(row.get("multi_tenant_collision_rooms", 0) or 0),
    }
