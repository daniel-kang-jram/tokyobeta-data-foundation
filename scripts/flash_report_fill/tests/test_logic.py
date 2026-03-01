from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from scripts.flash_report_fill.sql import (
    build_metric_queries,
    classify_tenant_type,
    is_active_at_snapshot,
)


def test_is_active_at_snapshot_moveout_equal_snapshot_is_inactive() -> None:
    snapshot = datetime(2026, 2, 1, 0, 0, 0, tzinfo=ZoneInfo("Asia/Tokyo"))

    assert is_active_at_snapshot(date(2026, 1, 1), None, snapshot) is True
    assert is_active_at_snapshot(date(2026, 1, 1), date(2026, 2, 2), snapshot) is True
    assert is_active_at_snapshot(date(2026, 1, 1), date(2026, 2, 1), snapshot) is False


def test_classify_tenant_type_mapping() -> None:
    assert classify_tenant_type(1) == "individual"
    assert classify_tenant_type(2) == "corporate"
    assert classify_tenant_type(3) == "corporate"
    assert classify_tenant_type(7) == "individual"
    assert classify_tenant_type(999) == "unknown"


def test_metric_query_uses_expected_moveout_fields() -> None:
    queries = build_metric_queries()

    completed_moveout_sql = queries["feb_completed_moveouts"].sql
    planned_moveout_sql = queries["feb_planned_moveouts"].sql

    assert "moveout_plans_date" in completed_moveout_sql
    assert "moveout_date > %(snapshot_asof)s" in planned_moveout_sql
    assert "management_status_code IN (14, 15, 16, 17)" in planned_moveout_sql


def test_metric_query_has_expected_window_operators() -> None:
    queries = build_metric_queries()

    completed_movein_sql = queries["feb_completed_moveins"].sql
    planned_movein_sql = queries["feb_planned_moveins"].sql

    assert "movein_date >= %(feb_start)s" in completed_movein_sql
    assert "movein_date <= %(snapshot_asof)s" in completed_movein_sql
    assert "original_movein_date > %(snapshot_asof)s" in planned_movein_sql
    assert "original_movein_date <= %(feb_end)s" in planned_movein_sql
    assert "management_status_code IN (4, 5, 6, 7, 9, 10, 11, 12, 13, 14, 15)" in planned_movein_sql


def test_metric_query_deduplicates_after_window_filter() -> None:
    queries = build_metric_queries()

    completed_movein_sql = queries["feb_completed_moveins"].sql

    assert "filtered_contracts AS (" in completed_movein_sql
    assert "deduplicated_filtered_contracts AS (" in completed_movein_sql
    assert completed_movein_sql.index("filtered_contracts AS (") < completed_movein_sql.index(
        "ROW_NUMBER() OVER ("
    )


def test_d5_fact_aligned_query_uses_is_moveout_and_room_priority() -> None:
    queries = build_metric_queries()
    d5_sql = queries["d5_occupied_rooms"].sql

    assert "is_moveout = 0" in d5_sql
    assert "management_status_code <> 7" in d5_sql
    assert "movein_date < %(snapshot_start)s" in d5_sql
    assert "PARTITION BY apartment_id, room_id" in d5_sql
