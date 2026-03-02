from __future__ import annotations

from datetime import date

import pytest

from scripts.flash_report_fill.reconciliation import (
    _silver_occupied_rooms,
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
        if "silver_asof_mar_planned_moveins" in sql:
            return {"planned_moveins_total": 293}
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

    def fetchall(self):
        sql = self.last_sql
        if "silver_asof_mar_planned_moveins_split" in sql:
            return [
                {"tenant_type": "individual", "cnt": 212},
                {"tenant_type": "corporate", "cnt": 81},
            ]
        return []


class _SilverFallbackCursor:
    def __init__(self):
        self.calls = []
        self.call_count = 0
        self.last_sql = ""

    def execute(self, sql, params):
        self.call_count += 1
        self.last_sql = sql
        self.calls.append((sql, params))
        if "is_room_primary = TRUE" in sql:
            raise RuntimeError(1054, "Unknown column 'is_room_primary' in 'where clause'")

    def fetchone(self):
        return {"occupied_rooms": 321}


class _SilverErrorCursor:
    def execute(self, sql, params):
        raise RuntimeError(2013, "Lost connection to MySQL server during query")

    def fetchone(self):
        return {"occupied_rooms": 0}


class _SilverUnexpectedButRecoverableCursor:
    def __init__(self):
        self.call_count = 0
        self.calls = []

    def execute(self, sql, params):
        self.call_count += 1
        self.calls.append((sql, params))
        if self.call_count == 1:
            raise RuntimeError(1205, "Lock wait timeout exceeded; try restarting transaction")

    def fetchone(self):
        return {"occupied_rooms": 654}


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
        reconciliation_asof_date=date(2026, 2, 28),
        mar_planned_movein_cells=["D13", "E13"],
    )

    assert len(rows) == 8
    assert rows[0].reconciliation_id == "silver_occupied_rooms"
    assert rows[0].asof_date == "2026-02-01"
    assert "snapshot_start date" in rows[0].note
    assert any(r.reconciliation_id == "silver_asof_mar_planned_moveins_total" for r in rows)
    assert any(r.reconciliation_id == "silver_asof_mar_planned_moveins_individual" for r in rows)
    assert any(r.reconciliation_id == "silver_asof_mar_planned_moveins_corporate" for r in rows)
    assert any("snapshot_date = %s" in sql and params == (date(2026, 2, 1),) for sql, params in cursor.calls)
    assert any(
        "silver_asof_mar_planned_moveins_split" in sql
        and params == (date(2026, 2, 28), date(2026, 2, 28), date(2026, 3, 31))
        for sql, params in cursor.calls
    )


def test_build_reconciliation_records_uses_selected_movein_prediction_date_column() -> None:
    cursor = _ReconCursor()
    rows = build_reconciliation_records(
        cursor=cursor,
        cell_values={"D5": 110, "D13": 11, "E13": 4},
        snapshot_start_date=date(2026, 2, 1),
        snapshot_asof_date=date(2026, 2, 26),
        feb_start_date=date(2026, 2, 1),
        feb_end_date=date(2026, 2, 28),
        mar_start_date=date(2026, 3, 1),
        mar_end_date=date(2026, 3, 31),
        reconciliation_asof_date=date(2026, 2, 28),
        mar_planned_movein_cells=["D13", "E13"],
        movein_prediction_date_column="movein_decided_date",
    )

    matching_sql = [
        sql for sql, _params in cursor.calls if "silver_asof_mar_planned_moveins_split" in sql
    ]
    assert len(matching_sql) == 1
    assert "m.movein_decided_date > %s" in matching_sql[0]
    assert "m.movein_decided_date <= %s" in matching_sql[0]
    assert "m.original_movein_date > %s" not in matching_sql[0]

    total_row = next(r for r in rows if r.reconciliation_id == "silver_asof_mar_planned_moveins_total")
    assert "movein_decided_date" in total_row.note


def test_build_reconciliation_records_rejects_unsupported_movein_prediction_date_column() -> None:
    cursor = _ReconCursor()
    with pytest.raises(ValueError, match="Unsupported move-in prediction column"):
        build_reconciliation_records(
            cursor=cursor,
            cell_values={"D5": 110, "D13": 11, "E13": 4},
            snapshot_start_date=date(2026, 2, 1),
            snapshot_asof_date=date(2026, 2, 26),
            feb_start_date=date(2026, 2, 1),
            feb_end_date=date(2026, 2, 28),
            mar_start_date=date(2026, 3, 1),
            mar_end_date=date(2026, 3, 31),
            reconciliation_asof_date=date(2026, 2, 28),
            mar_planned_movein_cells=["D13", "E13"],
            movein_prediction_date_column="movein_planned_at",
        )


def test_silver_occupied_rooms_uses_fallback_only_for_missing_is_room_primary_column() -> None:
    cursor = _SilverFallbackCursor()
    value = _silver_occupied_rooms(cursor, date(2026, 2, 1))
    assert value == 321
    assert cursor.call_count == 2
    assert "is_room_primary = TRUE" in cursor.calls[0][0]
    assert "WHERE snapshot_date = %s" in cursor.calls[1][0]


def test_silver_occupied_rooms_reraises_unexpected_database_errors() -> None:
    cursor = _SilverErrorCursor()
    try:
        _silver_occupied_rooms(cursor, date(2026, 2, 1))
        assert False, "expected RuntimeError to be raised"
    except RuntimeError as exc:
        assert exc.args[0] == 2013


def test_silver_occupied_rooms_does_not_fallback_for_non_missing_column_errors() -> None:
    cursor = _SilverUnexpectedButRecoverableCursor()
    with pytest.raises(RuntimeError) as excinfo:
        _silver_occupied_rooms(cursor, date(2026, 2, 1))
    assert excinfo.value.args[0] == 1205
    assert cursor.call_count == 1


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
