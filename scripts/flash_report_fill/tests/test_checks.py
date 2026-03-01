from __future__ import annotations

from scripts.flash_report_fill.checks import (
    build_double_active_rooms_sql,
    build_same_tenant_multi_status_sql,
    build_tenant_switch_gap_sql,
    run_anomaly_checks,
)


class _QueueCursor:
    def __init__(self, rows):
        self._rows = list(rows)
        self.sql_history = []

    def execute(self, sql, params):
        self.sql_history.append((sql, params))

    def fetchall(self):
        if self._rows:
            return self._rows.pop(0)
        return []


def test_check_sql_templates_include_expected_filters() -> None:
    sql_a = build_double_active_rooms_sql(10)
    sql_b = build_tenant_switch_gap_sql(10)
    sql_c = build_same_tenant_multi_status_sql(10)

    assert "COUNT(DISTINCT tenant_id) >= 2" in sql_a
    assert "DATEDIFF(next_movein_date, effective_moveout_at)" in sql_b
    assert "COUNT(DISTINCT s.management_status_code) > 1" in sql_c


def test_run_anomaly_checks_returns_warning_summary() -> None:
    cursor = _QueueCursor(
        rows=[
            [{"apartment_id": 1, "room_id": 2, "active_count": 2}],
            [],
            [{"tenant_id": 11, "status_variants": 2}],
        ]
    )

    checks, warnings = run_anomaly_checks(
        cursor=cursor,
        params={"snapshot_asof": "2026-02-26 05:00:00"},
        limit=50,
    )

    assert len(checks["double_active_rooms"]) == 1
    assert len(checks["tenant_switch_gaps"]) == 0
    assert len(checks["same_tenant_multi_status"]) == 1
    assert len(warnings) == 2
