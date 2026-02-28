"""
Unit tests for occupancy_kpi_updater.py

Covers:
- ensure_kpi_table_exists: DDL correctness
- compute_kpi_for_dates: historical vs future branching, metric calculations, upsert
- get_aurora_credentials: Secrets Manager integration
"""

import pathlib
import sys
import pytest
from datetime import date, timedelta
from unittest.mock import Mock, patch

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import occupancy_kpi_updater


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_cursor(as_of_date, *metric_counts):
    """
    Build a DictCursor-style Mock whose fetchone calls return:
      1. {'max_snapshot_date': as_of_date}
      2. {'count': metric_counts[0]}, {'count': metric_counts[1]}, ...
    """
    cursor = Mock()
    responses = [{"max_snapshot_date": as_of_date}] + [{"count": c} for c in metric_counts]
    cursor.fetchone.side_effect = responses
    return cursor


# ---------------------------------------------------------------------------
# ensure_kpi_table_exists
# ---------------------------------------------------------------------------

class TestEnsureKpiTableExists:

    def test_executes_create_table_statement(self):
        cursor = Mock()
        occupancy_kpi_updater.ensure_kpi_table_exists(cursor)
        cursor.execute.assert_called_once()

    def test_targets_gold_occupancy_daily_metrics(self):
        cursor = Mock()
        occupancy_kpi_updater.ensure_kpi_table_exists(cursor)
        sql = cursor.execute.call_args[0][0]
        assert "gold.occupancy_daily_metrics" in sql

    def test_uses_create_if_not_exists(self):
        cursor = Mock()
        occupancy_kpi_updater.ensure_kpi_table_exists(cursor)
        sql = cursor.execute.call_args[0][0]
        assert "CREATE TABLE IF NOT EXISTS" in sql

    def test_schema_includes_all_kpi_columns(self):
        cursor = Mock()
        occupancy_kpi_updater.ensure_kpi_table_exists(cursor)
        sql = cursor.execute.call_args[0][0]
        for col in [
            "snapshot_date",
            "applications",
            "new_moveins",
            "new_moveouts",
            "occupancy_delta",
            "period_start_rooms",
            "period_end_rooms",
            "occupancy_rate",
        ]:
            assert col in sql, f"Expected column '{col}' in CREATE TABLE DDL"

    def test_snapshot_date_is_primary_key(self):
        cursor = Mock()
        occupancy_kpi_updater.ensure_kpi_table_exists(cursor)
        sql = cursor.execute.call_args[0][0]
        assert "PRIMARY KEY (snapshot_date)" in sql


# ---------------------------------------------------------------------------
# compute_kpi_for_dates – edge cases
# ---------------------------------------------------------------------------

class TestComputeKpiForDatesEdgeCases:

    def test_returns_zero_for_empty_date_list(self):
        cursor = Mock()
        result = occupancy_kpi_updater.compute_kpi_for_dates(cursor, [])
        assert result == 0
        cursor.execute.assert_not_called()

    def test_raises_when_max_snapshot_is_none(self):
        cursor = Mock()
        cursor.fetchone.return_value = {"max_snapshot_date": None}
        with pytest.raises(RuntimeError, match="No data found in silver.tenant_room_snapshot_daily"):
            occupancy_kpi_updater.compute_kpi_for_dates(cursor, [date(2026, 2, 20)])

    def test_raises_when_fetchone_returns_none(self):
        """fetchone returning None (empty result set) must also raise."""
        cursor = Mock()
        cursor.fetchone.return_value = None
        with pytest.raises(RuntimeError):
            occupancy_kpi_updater.compute_kpi_for_dates(cursor, [date(2026, 2, 20)])

    def test_returns_count_of_processed_dates(self):
        as_of = date(2026, 2, 20)
        # historical date → apps, moveins, moveouts, period_start
        cursor = _make_cursor(as_of, 5, 3, 1, 9000)
        result = occupancy_kpi_updater.compute_kpi_for_dates(cursor, [as_of])
        assert result == 1

    def test_returns_count_for_multiple_dates(self):
        as_of = date(2026, 2, 20)
        dates = [as_of - timedelta(days=2), as_of - timedelta(days=1), as_of]
        responses = [{"max_snapshot_date": as_of}]
        for _ in dates:
            responses += [{"count": 1}, {"count": 1}, {"count": 0}, {"count": 8000}]
        cursor = Mock()
        cursor.fetchone.side_effect = responses
        assert occupancy_kpi_updater.compute_kpi_for_dates(cursor, dates) == 3


# ---------------------------------------------------------------------------
# compute_kpi_for_dates – historical path
# ---------------------------------------------------------------------------

class TestComputeKpiHistoricalDates:

    AS_OF = date(2026, 2, 20)

    def _run(self, apps, moveins, moveouts, period_start):
        cursor = _make_cursor(self.AS_OF, apps, moveins, moveouts, period_start)
        occupancy_kpi_updater.compute_kpi_for_dates(cursor, [self.AS_OF])
        return cursor

    def _all_sql(self, cursor):
        return [c.args[0] for c in cursor.execute.call_args_list if c.args]

    def test_queries_applications_for_historical_date(self):
        cursor = self._run(5, 3, 1, 9000)
        assert any("first_appearance" in s for s in self._all_sql(cursor))

    def test_uses_extended_status_codes_for_historical_moveins(self):
        cursor = self._run(5, 3, 1, 9000)
        # Historical move-ins include statuses 4,5,6,7,9
        assert any("(4, 5, 6, 7, 9)" in s for s in self._all_sql(cursor))

    def test_uses_moveout_plans_date_for_historical_moveouts(self):
        cursor = self._run(5, 3, 1, 9000)
        assert any("moveout_plans_date" in s for s in self._all_sql(cursor))

    def test_period_start_queries_silver_snapshot(self):
        cursor = self._run(5, 3, 1, 9000)
        # Historical period_start reads from silver snapshot, not gold
        sql_list = self._all_sql(cursor)
        assert any(
            "silver.tenant_room_snapshot_daily" in s
            and "management_status_code" in s
            for s in sql_list
        )

    def test_upsert_correct_applications(self):
        cursor = self._run(7, 3, 1, 9000)
        params = cursor.execute.call_args_list[-1].args[1]
        assert params[1] == 7  # applications

    def test_upsert_correct_new_moveins(self):
        cursor = self._run(5, 4, 1, 9000)
        params = cursor.execute.call_args_list[-1].args[1]
        assert params[2] == 4  # new_moveins

    def test_upsert_correct_new_moveouts(self):
        cursor = self._run(5, 3, 2, 9000)
        params = cursor.execute.call_args_list[-1].args[1]
        assert params[3] == 2  # new_moveouts

    def test_upsert_occupancy_delta_is_moveins_minus_moveouts(self):
        cursor = self._run(5, 6, 2, 9000)
        params = cursor.execute.call_args_list[-1].args[1]
        assert params[4] == 4  # occupancy_delta = 6 - 2

    def test_upsert_period_end_rooms_is_start_plus_delta(self):
        cursor = self._run(0, 5, 2, 9000)
        params = cursor.execute.call_args_list[-1].args[1]
        # delta = 5 - 2 = 3; end = 9000 + 3 = 9003
        assert params[5] == 9000  # period_start_rooms
        assert params[6] == 9003  # period_end_rooms

    def test_upsert_occupancy_rate_is_end_rooms_over_total(self):
        cursor = self._run(0, 0, 0, 8054)
        params = cursor.execute.call_args_list[-1].args[1]
        # 8054 / 16108 ≈ 0.5
        assert abs(params[7] - 0.5) < 0.001

    def test_upsert_uses_insert_on_duplicate_key_update(self):
        cursor = self._run(5, 3, 1, 9000)
        upsert_sql = cursor.execute.call_args_list[-1].args[0]
        assert "INSERT INTO gold.occupancy_daily_metrics" in upsert_sql
        assert "ON DUPLICATE KEY UPDATE" in upsert_sql

    def test_upsert_target_date_is_first_param(self):
        cursor = self._run(5, 3, 1, 9000)
        params = cursor.execute.call_args_list[-1].args[1]
        assert params[0] == self.AS_OF


# ---------------------------------------------------------------------------
# compute_kpi_for_dates – future path
# ---------------------------------------------------------------------------

class TestComputeKpiFutureDates:

    AS_OF = date(2026, 2, 20)
    FUTURE = date(2026, 2, 25)  # 5 days ahead

    def _run(self, moveins, moveouts, period_start):
        # Future: no applications query, so only 3 metric fetchone calls
        cursor = _make_cursor(self.AS_OF, moveins, moveouts, period_start)
        occupancy_kpi_updater.compute_kpi_for_dates(cursor, [self.FUTURE])
        return cursor

    def _all_sql(self, cursor):
        return [c.args[0] for c in cursor.execute.call_args_list if c.args]

    def test_does_not_query_applications(self):
        cursor = self._run(2, 1, 8800)
        assert not any("first_appearance" in s for s in self._all_sql(cursor))

    def test_upsert_applications_is_zero(self):
        cursor = self._run(2, 1, 8800)
        params = cursor.execute.call_args_list[-1].args[1]
        assert params[1] == 0  # applications always 0 for future

    def test_future_moveins_use_restricted_status_codes(self):
        """Future move-ins must only use statuses 4 and 5 (not 6, 7, 9)."""
        cursor = self._run(2, 1, 8800)
        sql_list = self._all_sql(cursor)
        # Should not find the historical extended status set
        assert not any("(4, 5, 6, 7, 9)" in s for s in sql_list)
        # Should find the future restricted status set
        assert any("(4, 5)" in s for s in sql_list)

    def test_future_moveouts_use_moveout_date_not_plans_date(self):
        cursor = self._run(2, 1, 8800)
        sql_list = self._all_sql(cursor)
        assert not any("moveout_plans_date" in s for s in sql_list)
        assert any("moveout_date" in s for s in sql_list)

    def test_future_move_ins_filtered_on_as_of_snapshot(self):
        """Future move-in query should use the as-of snapshot date, not the future date."""
        cursor = self._run(2, 1, 8800)
        # Find the move-in query (contains move_in_date)
        movein_calls = [
            c for c in cursor.execute.call_args_list
            if c.args and "move_in_date" in c.args[0]
        ]
        assert movein_calls, "Expected a move_in_date query"
        params = movein_calls[0].args[1]
        # First param is snapshot_date_filter (as_of), second is the future target date
        assert params[0] == self.AS_OF
        assert params[1] == self.FUTURE

    def test_future_period_start_still_reads_silver_snapshot(self):
        """In occupancy_kpi_updater, period_start for future dates uses silver (not gold)."""
        cursor = self._run(2, 1, 8800)
        sql_list = self._all_sql(cursor)
        assert any(
            "silver.tenant_room_snapshot_daily" in s
            and "management_status_code" in s
            for s in sql_list
        )

    def test_upsert_correct_future_metrics(self):
        cursor = self._run(3, 1, 8800)
        params = cursor.execute.call_args_list[-1].args[1]
        assert params[2] == 3    # new_moveins
        assert params[3] == 1    # new_moveouts
        assert params[4] == 2    # occupancy_delta = 3 - 1
        assert params[5] == 8800 # period_start_rooms
        assert params[6] == 8802 # period_end_rooms = 8800 + 2


# ---------------------------------------------------------------------------
# get_aurora_credentials
# ---------------------------------------------------------------------------

class TestGetAuroraCredentials:

    def test_returns_username_and_password(self, monkeypatch):
        mock_sm = Mock()
        mock_sm.get_secret_value.return_value = {
            "SecretString": '{"username": "admin", "password": "s3cr3t"}'
        }
        monkeypatch.setattr(occupancy_kpi_updater, "secretsmanager", mock_sm)
        monkeypatch.setitem(occupancy_kpi_updater.args, "AURORA_SECRET_ARN", "arn:test")

        username, password = occupancy_kpi_updater.get_aurora_credentials()

        assert username == "admin"
        assert password == "s3cr3t"

    def test_uses_secret_arn_from_args(self, monkeypatch):
        mock_sm = Mock()
        mock_sm.get_secret_value.return_value = {
            "SecretString": '{"username": "u", "password": "p"}'
        }
        monkeypatch.setattr(occupancy_kpi_updater, "secretsmanager", mock_sm)
        monkeypatch.setitem(occupancy_kpi_updater.args, "AURORA_SECRET_ARN", "arn:aws:custom-arn")

        occupancy_kpi_updater.get_aurora_credentials()

        mock_sm.get_secret_value.assert_called_once_with(SecretId="arn:aws:custom-arn")

    def test_parses_json_secret_string(self, monkeypatch):
        mock_sm = Mock()
        mock_sm.get_secret_value.return_value = {
            "SecretString": '{"username": "db_user", "password": "p@ss!word"}'
        }
        monkeypatch.setattr(occupancy_kpi_updater, "secretsmanager", mock_sm)
        monkeypatch.setitem(occupancy_kpi_updater.args, "AURORA_SECRET_ARN", "arn:test")

        username, password = occupancy_kpi_updater.get_aurora_credentials()

        assert username == "db_user"
        assert password == "p@ss!word"
