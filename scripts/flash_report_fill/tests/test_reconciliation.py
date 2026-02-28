from __future__ import annotations

from datetime import date

from scripts.flash_report_fill.reconciliation import (
    build_reconciliation_records,
    metrics_records_to_csv_rows,
    reconciliation_records_to_csv_rows,
)
from scripts.flash_report_fill.types import MetricRecord, ReconciliationRecord


def test_metrics_records_to_csv_rows_has_required_columns() -> None:
    records = [
        MetricRecord(
            metric_id="d5_occupied_rooms",
            sheet="Flash Report（2月）",
            cell="D5",
            value=12345,
            month="2026-02",
            tenant_type="all",
            window_start="2026-02-01 00:00:00+09:00",
            window_end="2026-02-01 00:00:00+09:00",
            asof_ts_jst="2026-02-26 05:00:00+09:00",
            source_layer="staging",
            query_tag="metric:d5",
            query_sql="SELECT 1",
        )
    ]

    rows = metrics_records_to_csv_rows(records)
    assert len(rows) == 1
    row = rows[0]

    required = {
        "metric_id",
        "sheet",
        "cell",
        "value",
        "month",
        "tenant_type",
        "window_start",
        "window_end",
        "asof_ts_jst",
        "source_layer",
        "query_tag",
        "query_sql",
    }
    assert required.issubset(set(row.keys()))


def test_reconciliation_records_to_csv_rows_shape() -> None:
    records = [
        ReconciliationRecord(
            reconciliation_id="gold_feb_moveins_total",
            expected_value=10,
            reference_value=8,
            delta=2,
            reference_source="gold.occupancy_daily_metrics",
            note="semantic delta",
            asof_date="2026-02-26",
        )
    ]

    rows = reconciliation_records_to_csv_rows(records)
    assert rows[0]["reconciliation_id"] == "gold_feb_moveins_total"
    assert rows[0]["delta"] == 2


class _ReconCursor:
    def __init__(self):
        self.last_sql = ""

    def execute(self, sql, params):
        self.last_sql = sql

    def fetchone(self):
        sql = self.last_sql
        if "MAX(snapshot_date)" in sql:
            return {"snapshot_date": date(2026, 2, 26)}
        if "is_room_primary = TRUE" in sql:
            return {"occupied_rooms": 111}
        if "SUM(new_moveins)" in sql:
            return {"moveins": 200, "moveouts": 150}
        return {"occupied_rooms": 111}


def test_build_reconciliation_records_returns_expected_rows() -> None:
    cursor = _ReconCursor()
    rows = build_reconciliation_records(
        cursor=cursor,
        cell_values={
            "D5": 110,
            "D11": 10,
            "E11": 5,
            "D12": 8,
            "E12": 2,
            "D15": 7,
            "E15": 1,
            "D16": 9,
            "E16": 3,
            "D13": 11,
            "E13": 4,
            "D14": 5,
            "E14": 1,
            "D17": 6,
            "E17": 2,
        },
        snapshot_asof_date=date(2026, 2, 26),
        feb_start_date=date(2026, 2, 1),
        feb_end_date=date(2026, 2, 28),
        mar_start_date=date(2026, 3, 1),
        mar_end_date=date(2026, 3, 31),
    )

    assert len(rows) == 5
    assert rows[0].reconciliation_id == "silver_occupied_rooms"
