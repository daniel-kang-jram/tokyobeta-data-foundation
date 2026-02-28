from __future__ import annotations

from datetime import date
from typing import Dict, Iterable, List

from scripts.flash_report_fill.types import MetricRecord, ReconciliationRecord


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
