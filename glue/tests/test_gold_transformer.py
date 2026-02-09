"""
Test suite for gold_transformer.py
Following TDD principles: Write tests FIRST, then implement.
"""

import pytest
import json
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta


# Import will fail initially - expected in TDD (RED phase)
try:
    import sys
    sys.path.insert(0, '../scripts')
    from gold_transformer import (
        run_dbt_gold_models,
        run_dbt_gold_tests,
        create_table_backups,
        cleanup_old_backups
    )
except ImportError:
    pass


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


# Run tests with: pytest glue/tests/test_gold_transformer.py -v
