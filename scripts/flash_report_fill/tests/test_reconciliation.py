from __future__ import annotations

from datetime import date

from scripts.flash_report_fill.reconciliation import (
    build_d5_discrepancy_records,
    build_reconciliation_records,
    metrics_records_to_csv_rows,
    reconciliation_records_to_csv_rows,
)
from scripts.flash_report_fill.types import MetricRecord, ReconciliationRecord, WarningRecord


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
        self.last_params = None
        self.calls = []

    def execute(self, sql, params):
        self.last_sql = sql
        self.last_params = params
        self.calls.append((sql, params))

    def fetchone(self):
        sql = self.last_sql
        if "is_room_primary = TRUE" in sql:
            return {"occupied_rooms": 111}
        if "SUM(new_moveins)" in sql:
            return {"moveins": 200, "moveouts": 150}
        if "d5_fact_aligned_count" in sql:
            return {"d5_fact_aligned_count": 11273}
        if "d5_discrepancy_categories" in sql:
            return {
                "status7_midnight_adjusted_rooms": 23,
                "fact_multi_tenant_collision_rooms": 77,
            }
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
        snapshot_start_date=date(2026, 2, 1),
        snapshot_asof_date=date(2026, 2, 26),
        feb_start_date=date(2026, 2, 1),
        feb_end_date=date(2026, 2, 28),
        mar_start_date=date(2026, 3, 1),
        mar_end_date=date(2026, 3, 31),
    )

    assert len(rows) == 5
    assert rows[0].reconciliation_id == "silver_occupied_rooms"
    assert rows[0].asof_date == "2026-02-01"
    assert "snapshot_start date" in rows[0].note
    assert any("snapshot_date = %s" in sql and params == (date(2026, 2, 1),) for sql, params in cursor.calls)


def test_build_d5_discrepancy_records_returns_records_and_warning() -> None:
    cursor = _ReconCursor()
    records, warnings = build_d5_discrepancy_records(
        cursor=cursor,
        snapshot_start_ts="2026-02-01 00:00:00",
        snapshot_start_date=date(2026, 2, 1),
        benchmark_value=11271,
        tolerance=10,
    )

    assert [r.reconciliation_id for r in records] == [
        "d5_fact_aligned_vs_benchmark",
        "d5_discrepancy_status7_midnight_adjusted_rooms",
        "d5_discrepancy_fact_multi_tenant_collision_rooms",
    ]
    assert records[0].reference_value == 11273
    assert records[1].reference_value == 23
    assert records[2].reference_value == 77
    assert warnings == []


def test_build_d5_discrepancy_records_warns_when_fact_aligned_exceeds_tolerance() -> None:
    cursor = _ReconCursor()
    _, warnings = build_d5_discrepancy_records(
        cursor=cursor,
        snapshot_start_ts="2026-02-01 00:00:00",
        snapshot_start_date=date(2026, 2, 1),
        benchmark_value=11271,
        tolerance=1,
    )

    assert warnings == [
        WarningRecord(
            code="WARN_D5_FACT_ALIGNED_BENCHMARK_DELTA",
            message="D5 fact-aligned result differs from benchmark beyond tolerance.",
            count=2,
        )
    ]
