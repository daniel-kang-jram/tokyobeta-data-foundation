"""
Test suite for gold_transformer.py
Following TDD principles: Write tests FIRST, then implement.
"""

import pathlib
import pytest
import json
import sys
from unittest.mock import MagicMock, Mock, patch
from datetime import date, datetime, timedelta

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from gold_transformer import (
    run_dbt_gold_models,
    run_dbt_gold_tests,
    create_table_backups,
    cleanup_old_backups,
    ensure_occupancy_kpi_table_exists,
    compute_occupancy_kpis,
)


class TestRunDbtGoldModels:
    """Test dbt gold models execution."""
    
    @patch('subprocess.run')
    def test_runs_gold_models_only(self, mock_run, mock_dbt_result):
        """Should run only gold.* models."""
        mock_run.return_value = mock_dbt_result
        
        result = run_dbt_gold_models('/tmp/dbt', 'prod')
        
        args = mock_run.call_args[0][0]
        assert 'run' in args
        assert '--models' in args
        models_idx = args.index('--models')
        assert 'gold' in args[models_idx + 1]
    
    @patch('subprocess.run')
    def test_uses_fail_fast(self, mock_run, mock_dbt_result):
        """Should use --fail-fast flag."""
        mock_run.return_value = mock_dbt_result
        
        result = run_dbt_gold_models('/tmp/dbt', 'prod')
        
        args = mock_run.call_args[0][0]
        assert '--fail-fast' in args
    
    @patch('subprocess.run')
    def test_returns_model_count(self, mock_run):
        """Should return count of gold models built."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Completed successfully\n6 of 6 models built"
        )
        
        result = run_dbt_gold_models('/tmp/dbt', 'prod')
        
        assert result['models_built'] >= 6


class TestRunDbtGoldTests:
    """Test dbt gold tests execution."""
    
    @patch('subprocess.run')
    def test_runs_gold_tests_only(self, mock_run, mock_dbt_result):
        """Should run only gold.* tests."""
        mock_run.return_value = mock_dbt_result
        
        result = run_dbt_gold_tests('/tmp/dbt', 'prod')
        
        args = mock_run.call_args[0][0]
        assert 'test' in args
        assert '--models' in args
    
    @patch('subprocess.run')
    def test_continues_on_test_failures(self, mock_run):
        """Should not raise error on test failures."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="58 tests passed, 5 failed"
        )
        
        result = run_dbt_gold_tests('/tmp/dbt', 'prod')
        
        assert result['tests_passed'] > 0
        assert result['tests_failed'] > 0


class TestCleanupOldBackups:
    """Test old backup cleanup."""
    
    def test_removes_backups_older_than_retention(self, mock_aurora_connection):
        """Should remove backups older than retention period."""
        cursor = mock_aurora_connection.cursor()
        
        # Mock old backups (4+ days old)
        old_date = (datetime.now() - timedelta(days=4)).strftime('%Y%m%d')
        cursor.fetchall.return_value = [
            (f'int_contracts_backup_{old_date}_123456',),
            (f'moveouts_backup_{old_date}_234567',)
        ]
        
        with patch('pymysql.connect', return_value=mock_aurora_connection):
            removed_count = cleanup_old_backups(
                mock_aurora_connection,
                days_to_keep=3
            )
        
        assert removed_count == 2
        assert any('DROP TABLE' in str(call) for call in cursor.execute.call_args_list)
    
    def test_keeps_recent_backups(self, mock_aurora_connection):
        """Should keep backups within retention period."""
        cursor = mock_aurora_connection.cursor()
        
        # Mock recent backups (1 day old)
        recent_date = (datetime.now() - timedelta(days=1)).strftime('%Y%m%d')
        cursor.fetchall.return_value = [
            (f'int_contracts_backup_{recent_date}_123456',),
        ]
        
        with patch('pymysql.connect', return_value=mock_aurora_connection):
            removed_count = cleanup_old_backups(
                mock_aurora_connection,
                days_to_keep=3
            )
        
        assert removed_count == 0
    
    def test_handles_multiple_schemas(self, mock_aurora_connection):
        """Should clean up backups in both silver and gold schemas."""
        cursor = mock_aurora_connection.cursor()
        old_date = (datetime.now() - timedelta(days=5)).strftime('%Y%m%d')
        
        # Return different backups for each schema query
        cursor.fetchall.side_effect = [
            [(f'silver_table_backup_{old_date}_111111',)],  # silver schema
            [(f'gold_table_backup_{old_date}_222222',)]     # gold schema
        ]
        
        with patch('pymysql.connect', return_value=mock_aurora_connection):
            removed_count = cleanup_old_backups(
                mock_aurora_connection,
                days_to_keep=3
            )
        
        assert removed_count >= 2


class TestEnsureOccupancyKpiTableExists:
    """Test gold_transformer's DDL guard for occupancy_daily_metrics."""

    def test_executes_create_table(self):
        cursor = Mock()
        ensure_occupancy_kpi_table_exists(cursor)
        cursor.execute.assert_called_once()

    def test_targets_gold_schema(self):
        cursor = Mock()
        ensure_occupancy_kpi_table_exists(cursor)
        sql = cursor.execute.call_args[0][0]
        assert "gold.occupancy_daily_metrics" in sql

    def test_uses_create_if_not_exists(self):
        cursor = Mock()
        ensure_occupancy_kpi_table_exists(cursor)
        sql = cursor.execute.call_args[0][0]
        assert "CREATE TABLE IF NOT EXISTS" in sql

    def test_all_kpi_columns_present(self):
        cursor = Mock()
        ensure_occupancy_kpi_table_exists(cursor)
        sql = cursor.execute.call_args[0][0]
        for col in [
            "snapshot_date", "applications", "new_moveins", "new_moveouts",
            "occupancy_delta", "period_start_rooms", "period_end_rooms", "occupancy_rate",
        ]:
            assert col in sql, f"Column '{col}' missing from DDL"

    def test_snapshot_date_is_primary_key(self):
        cursor = Mock()
        ensure_occupancy_kpi_table_exists(cursor)
        sql = cursor.execute.call_args[0][0]
        assert "PRIMARY KEY (snapshot_date)" in sql


class TestComputeOccupancyKpisHistorical:
    """
    Tests for compute_occupancy_kpis (gold_transformer) – historical date path.

    The function creates its own cursor via connection.cursor(DictCursor),
    calls ensure_occupancy_kpi_table_exists (one extra execute), then processes
    each date.  fetchone sequence for a single historical date:
        [{'max_snapshot_date': as_of}, {'count': apps}, {'count': moveins},
         {'count': moveouts}, {'count': period_start}]
    """

    AS_OF = date(2026, 2, 20)

    def _run(self, apps, moveins, moveouts, period_start, lookback=0, forward=0):
        cursor = Mock()
        cursor.fetchone.side_effect = [
            {"max_snapshot_date": self.AS_OF},
            {"count": apps},
            {"count": moveins},
            {"count": moveouts},
            {"count": period_start},
        ]
        connection = Mock()
        connection.cursor.return_value = cursor
        # lookback=0, forward=0 → only process the as_of date itself
        compute_occupancy_kpis(connection, lookback_days=lookback, forward_days=forward)
        return cursor, connection

    def _all_sql(self, cursor):
        return [c.args[0] for c in cursor.execute.call_args_list if c.args]

    def test_calls_ensure_table_exists(self):
        cursor, _ = self._run(5, 3, 1, 9000)
        assert any("CREATE TABLE IF NOT EXISTS" in s for s in self._all_sql(cursor))

    def test_commits_after_table_creation(self):
        _, connection = self._run(5, 3, 1, 9000)
        assert connection.commit.call_count >= 1

    def test_queries_applications_for_historical_date(self):
        cursor, _ = self._run(5, 3, 1, 9000)
        assert any("first_appearance" in s for s in self._all_sql(cursor))

    def test_uses_extended_status_codes_for_moveins(self):
        cursor, _ = self._run(5, 3, 1, 9000)
        assert any("(4, 5, 6, 7, 9)" in s for s in self._all_sql(cursor))

    def test_uses_moveout_plans_date_for_historical_moveouts(self):
        cursor, _ = self._run(5, 3, 1, 9000)
        assert any("moveout_plans_date" in s for s in self._all_sql(cursor))

    def test_upsert_inserts_into_gold_occupancy_daily_metrics(self):
        cursor, _ = self._run(5, 3, 1, 9000)
        upsert_sql = cursor.execute.call_args_list[-1].args[0]
        assert "INSERT INTO gold.occupancy_daily_metrics" in upsert_sql
        assert "ON DUPLICATE KEY UPDATE" in upsert_sql

    def test_upsert_correct_metric_values(self):
        cursor, _ = self._run(apps=5, moveins=4, moveouts=2, period_start=9000)
        params = cursor.execute.call_args_list[-1].args[1]
        # (snapshot_date, applications, new_moveins, new_moveouts,
        #  occupancy_delta, period_start_rooms, period_end_rooms, occupancy_rate)
        assert params[1] == 5      # applications
        assert params[2] == 4      # new_moveins
        assert params[3] == 2      # new_moveouts
        assert params[4] == 2      # occupancy_delta = 4 - 2
        assert params[5] == 9000   # period_start_rooms
        assert params[6] == 9002   # period_end_rooms = 9000 + 2

    def test_upsert_occupancy_rate(self):
        # 8054 occupied / 16108 total = exactly 0.5
        cursor, _ = self._run(0, 0, 0, 8054)
        params = cursor.execute.call_args_list[-1].args[1]
        assert abs(params[7] - 0.5) < 0.001

    def test_closes_cursor_on_completion(self):
        cursor, _ = self._run(5, 3, 1, 9000)
        cursor.close.assert_called_once()


class TestComputeOccupancyKpisFuture:
    """
    Tests for compute_occupancy_kpis (gold_transformer) – future date path.

    KEY DIFFERENCE from occupancy_kpi_updater:
    For future dates, period_start_rooms is read from gold.occupancy_daily_metrics
    (the previous day's period_end_rooms), NOT from the silver snapshot.

    fetchone sequence for a single future date (as_of + 1 day, forward=1):
        [{'max_snapshot_date': as_of},    # MAX query
         {'count': moveins},              # future move-in query
         {'count': moveouts},             # future move-out query
         {'period_end_rooms': period_start}]  # gold KPI table for previous day
    """

    AS_OF = date(2026, 2, 20)
    FUTURE = date(2026, 2, 21)  # as_of + 1

    def _run(self, moveins, moveouts, period_start):
        cursor = Mock()
        cursor.fetchone.side_effect = [
            {"max_snapshot_date": self.AS_OF},  # MAX query
            {"count": moveins},                  # future move-ins
            {"count": moveouts},                 # future move-outs
            {"period_end_rooms": period_start},  # gold KPI chain
        ]
        connection = Mock()
        connection.cursor.return_value = cursor
        # lookback=0, forward=1 → processes as_of (historical) and as_of+1 (future)
        # We only care about the future date processing; supply enough fetchone for both.
        # Simplest: run with lookback=0, forward=0 on a future-only list.
        # Instead, patch the function to process only the future date.
        # Re-build with enough responses for as_of (historical) + future:
        cursor.fetchone.side_effect = [
            {"max_snapshot_date": self.AS_OF},
            # as_of historical: apps, moveins, moveouts, period_start
            {"count": 0}, {"count": 0}, {"count": 0}, {"count": 9000},
            # FUTURE: moveins, moveouts, period_start from gold
            {"count": moveins}, {"count": moveouts}, {"period_end_rooms": period_start},
        ]
        compute_occupancy_kpis(connection, lookback_days=0, forward_days=1)
        return cursor, connection

    def _all_sql(self, cursor):
        return [c.args[0] for c in cursor.execute.call_args_list if c.args]

    def test_future_applications_not_queried(self):
        cursor, _ = self._run(2, 1, 8800)
        # The applications subquery should only appear once (for the historical as_of date)
        first_appearance_count = sum(
            1 for s in self._all_sql(cursor) if "first_appearance" in s
        )
        assert first_appearance_count == 1  # only historical date

    def test_future_moveins_use_restricted_status_codes(self):
        cursor, _ = self._run(2, 1, 8800)
        # future move-in query targets statuses (4, 5) only
        restricted_moveins = [
            s for s in self._all_sql(cursor)
            if "move_in_date" in s and "(4, 5)" in s and "(4, 5, 6, 7, 9)" not in s
        ]
        assert restricted_moveins, "Expected a future move-in query with status IN (4, 5)"

    def test_future_moveouts_use_moveout_date(self):
        cursor, _ = self._run(2, 1, 8800)
        future_moveout_queries = [
            s for s in self._all_sql(cursor) if "moveout_date" in s and "moveout_plans_date" not in s
        ]
        assert future_moveout_queries, "Expected a future moveout query using moveout_date"

    def test_future_period_start_reads_from_gold_not_silver(self):
        """
        This is the divergence from occupancy_kpi_updater: gold_transformer reads
        period_start_rooms from gold.occupancy_daily_metrics for future dates.
        """
        cursor, _ = self._run(2, 1, 8800)
        gold_period_queries = [
            s for s in self._all_sql(cursor)
            if "gold.occupancy_daily_metrics" in s and "period_end_rooms" in s
        ]
        assert gold_period_queries, (
            "Future period_start should read period_end_rooms from gold.occupancy_daily_metrics"
        )

    def test_future_upsert_applications_is_zero(self):
        cursor, _ = self._run(3, 1, 8800)
        # The last upsert call corresponds to the future date
        future_upsert = cursor.execute.call_args_list[-1]
        params = future_upsert.args[1]
        assert params[1] == 0  # applications

    def test_future_upsert_correct_metrics(self):
        cursor, _ = self._run(moveins=3, moveouts=1, period_start=8800)
        params = cursor.execute.call_args_list[-1].args[1]
        assert params[2] == 3     # new_moveins
        assert params[3] == 1     # new_moveouts
        assert params[4] == 2     # occupancy_delta = 3 - 1
        assert params[5] == 8800  # period_start_rooms (from gold)
        assert params[6] == 8802  # period_end_rooms = 8800 + 2

    def test_raises_when_no_snapshot_data(self):
        cursor = Mock()
        cursor.fetchone.return_value = {"max_snapshot_date": None}
        connection = Mock()
        connection.cursor.return_value = cursor
        with pytest.raises(RuntimeError, match="No data found in silver.tenant_room_snapshot_daily"):
            compute_occupancy_kpis(connection, lookback_days=0, forward_days=0)


# Run tests with: pytest glue/tests/test_gold_transformer.py -v
