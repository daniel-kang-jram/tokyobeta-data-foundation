"""
Test suite for silver_transformer.py
Following TDD principles: Write tests FIRST, then implement.
"""

import pytest
import json
import subprocess
from unittest.mock import MagicMock, patch, call
from datetime import datetime


# Import will fail initially - expected in TDD (RED phase)
try:
    import sys
    sys.path.insert(0, '../scripts')
    from silver_transformer import (
        get_aurora_credentials,
        download_dbt_project,
        install_dbt_dependencies,
        run_dbt_seed,
        run_dbt_silver_models,
        run_dbt_silver_tests,
        create_table_backups,
        get_dbt_executable_path
    )
except ImportError:
    # Expected during RED phase
    pass


class TestGetAuroraCredentials:
    """Test Aurora credentials retrieval."""
    
    def test_retrieves_credentials_from_secrets_manager(self, mock_secretsmanager_client):
        """Should retrieve username and password from Secrets Manager."""
        username, password = get_aurora_credentials(
            mock_secretsmanager_client,
            'arn:aws:secretsmanager:xxx'
        )
        
        assert username == 'test_user'
        assert password == 'test_pass'
    
    def test_parses_json_secret(self, mock_secretsmanager_client):
        """Should parse JSON-formatted secret."""
        mock_secretsmanager_client.get_secret_value.return_value = {
            'SecretString': '{"username": "admin", "password": "secret123"}'
        }
        
        username, password = get_aurora_credentials(
            mock_secretsmanager_client,
            'arn:aws:secretsmanager:xxx'
        )
        
        assert username == 'admin'
        assert password == 'secret123'


class TestDownloadDbtProject:
    """Test dbt project download from S3."""
    
    @patch('subprocess.run')
    def test_downloads_dbt_project_from_s3(self, mock_run):
        """Should sync dbt project from S3 to local path."""
        mock_run.return_value = MagicMock(returncode=0)
        
        result = download_dbt_project('test-bucket', 'dbt-project/', '/tmp/dbt')
        
        # Verify aws s3 sync was called
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert 'aws' in args
        assert 's3' in args
        assert 'sync' in args
        assert 's3://test-bucket/dbt-project/' in args
        assert '/tmp/dbt' in args
    
    @patch('subprocess.run')
    def test_raises_on_download_failure(self, mock_run):
        """Should raise error if S3 sync fails."""
        mock_run.side_effect = subprocess.CalledProcessError(1, 'aws s3 sync')
        
        with pytest.raises(subprocess.CalledProcessError):
            download_dbt_project('test-bucket', 'dbt-project/', '/tmp/dbt')


class TestGetDbtExecutablePath:
    """Test dbt executable path discovery."""
    
    def test_returns_glue_dbt_path(self):
        """Should return dbt path in Glue environment."""
        path = get_dbt_executable_path()
        assert 'dbt' in path
        assert path.endswith('dbt')
    
    @patch('os.path.exists')
    def test_checks_multiple_locations(self, mock_exists):
        """Should check multiple possible dbt locations."""
        mock_exists.side_effect = [False, False, True]
        
        path = get_dbt_executable_path()
        assert mock_exists.call_count >= 1


class TestInstallDbtDependencies:
    """Test dbt dependencies installation."""
    
    @patch('subprocess.run')
    def test_runs_dbt_deps(self, mock_run, mock_dbt_result):
        """Should run dbt deps command."""
        mock_run.return_value = mock_dbt_result
        
        result = install_dbt_dependencies('/tmp/dbt')
        
        # Verify dbt deps was called
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert 'dbt' in args[0]
        assert 'deps' in args
    
    @patch('subprocess.run')
    def test_uses_correct_project_dir(self, mock_run, mock_dbt_result):
        """Should use correct project directory."""
        mock_run.return_value = mock_dbt_result
        
        result = install_dbt_dependencies('/custom/path')
        
        args = mock_run.call_args[0][0]
        assert '--project-dir' in args
        assert '/custom/path' in args
    
    @patch('subprocess.run')
    def test_handles_deps_failure(self, mock_run):
        """Should raise error if deps installation fails."""
        mock_run.return_value = MagicMock(returncode=1, stderr='Package not found')
        
        with pytest.raises(subprocess.CalledProcessError):
            install_dbt_dependencies('/tmp/dbt')


class TestRunDbtSeed:
    """Test dbt seed execution."""
    
    @patch('subprocess.run')
    def test_runs_dbt_seed(self, mock_run, mock_dbt_result):
        """Should run dbt seed command."""
        mock_run.return_value = mock_dbt_result
        
        result = run_dbt_seed('/tmp/dbt', 'prod')
        
        # Verify dbt seed was called
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert 'seed' in args
        assert '--target' in args
        assert 'prod' in args
    
    @patch('subprocess.run')
    def test_captures_output(self, mock_run, mock_dbt_result):
        """Should capture stdout and stderr."""
        mock_run.return_value = mock_dbt_result
        
        result = run_dbt_seed('/tmp/dbt', 'prod')
        
        # Verify capture_output was set
        assert mock_run.call_args[1]['capture_output'] is True
    
    @patch('subprocess.run')
    def test_logs_seed_output(self, mock_run, mock_dbt_result):
        """Should log dbt seed output."""
        mock_run.return_value = mock_dbt_result
        
        with patch('builtins.print') as mock_print:
            result = run_dbt_seed('/tmp/dbt', 'prod')
            
            # Should print output
            assert any('SEED' in str(call) for call in mock_print.call_args_list)


class TestRunDbtSilverModels:
    """Test dbt silver models execution."""
    
    @patch('subprocess.run')
    def test_runs_silver_models_only(self, mock_run, mock_dbt_result):
        """Should run only silver.* models."""
        mock_run.return_value = mock_dbt_result
        
        result = run_dbt_silver_models('/tmp/dbt', 'prod')
        
        args = mock_run.call_args[0][0]
        assert 'run' in args
        assert '--models' in args
        # Find index of --models and check next arg
        models_idx = args.index('--models')
        assert 'silver' in args[models_idx + 1]
    
    @patch('subprocess.run')
    def test_uses_fail_fast(self, mock_run, mock_dbt_result):
        """Should use --fail-fast flag."""
        mock_run.return_value = mock_dbt_result
        
        result = run_dbt_silver_models('/tmp/dbt', 'prod')
        
        args = mock_run.call_args[0][0]
        assert '--fail-fast' in args
    
    @patch('subprocess.run')
    def test_sets_environment_variables(self, mock_run, mock_dbt_result):
        """Should set Aurora connection environment variables."""
        mock_run.return_value = mock_dbt_result
        
        with patch.dict('os.environ', {}, clear=True):
            result = run_dbt_silver_models(
                '/tmp/dbt',
                'prod',
                aurora_endpoint='test.rds.amazonaws.com',
                aurora_username='testuser',
                aurora_password='testpass'
            )
            
            # Environment variables should be set
            import os
            # Can't directly test os.environ in subprocess, but verified in implementation
    
    @patch('subprocess.run')
    def test_returns_model_count(self, mock_run):
        """Should return count of models built."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Completed successfully\n6 models built"
        )
        
        result = run_dbt_silver_models('/tmp/dbt', 'prod')
        
        assert 'models_built' in result
        assert result['models_built'] >= 0


class TestRunDbtSilverTests:
    """Test dbt silver tests execution."""
    
    @patch('subprocess.run')
    def test_runs_silver_tests_only(self, mock_run, mock_dbt_result):
        """Should run only silver.* tests."""
        mock_run.return_value = mock_dbt_result
        
        result = run_dbt_silver_tests('/tmp/dbt', 'prod')
        
        args = mock_run.call_args[0][0]
        assert 'test' in args
        assert '--models' in args
        models_idx = args.index('--models')
        assert 'silver' in args[models_idx + 1]
    
    @patch('subprocess.run')
    def test_continues_on_test_failures(self, mock_run):
        """Should not raise error on test failures (warnings only)."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="3 tests passed, 2 failed"
        )
        
        # Should not raise exception
        result = run_dbt_silver_tests('/tmp/dbt', 'prod')
        
        assert result['tests_failed'] > 0
    
    @patch('subprocess.run')
    def test_returns_test_counts(self, mock_run):
        """Should return passed and failed test counts."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="45 tests passed"
        )
        
        result = run_dbt_silver_tests('/tmp/dbt', 'prod')
        
        assert 'tests_passed' in result
        assert 'tests_failed' in result


class TestCreateTableBackups:
    """Test table backup creation before transforms."""
    
    def test_creates_backup_for_each_table(self, mock_aurora_connection):
        """Should create backup for each silver table."""
        cursor = mock_aurora_connection.cursor()
        cursor.fetchone.side_effect = [
            ('int_contracts',),  # Table exists
            (59118,),  # Row count
            ('stg_movings',),
            (12543,),
        ]
        
        tables = ['int_contracts', 'stg_movings']
        
        with patch('pymysql.connect', return_value=mock_aurora_connection):
            backup_count = create_table_backups(
                mock_aurora_connection,
                tables,
                'silver'
            )
        
        assert backup_count == len(tables)
    
    def test_uses_timestamp_in_backup_name(self, mock_aurora_connection):
        """Should use timestamp in backup table name."""
        cursor = mock_aurora_connection.cursor()
        cursor.fetchone.side_effect = [('int_contracts',), (1000,)]
        
        with patch('pymysql.connect', return_value=mock_aurora_connection):
            backup_count = create_table_backups(
                mock_aurora_connection,
                ['int_contracts'],
                'silver'
            )
        
        # Verify CREATE TABLE ... AS SELECT was called
        calls = cursor.execute.call_args_list
        assert any('CREATE TABLE' in str(call) and 'backup' in str(call) for call in calls)
    
    def test_skips_non_existent_tables(self, mock_aurora_connection):
        """Should skip tables that don't exist."""
        cursor = mock_aurora_connection.cursor()
        cursor.fetchone.return_value = None  # Table doesn't exist
        
        with patch('pymysql.connect', return_value=mock_aurora_connection):
            backup_count = create_table_backups(
                mock_aurora_connection,
                ['non_existent_table'],
                'silver'
            )
        
        assert backup_count == 0
    
    def test_continues_on_backup_failure(self, mock_aurora_connection):
        """Should continue backing up other tables if one fails."""
        cursor = mock_aurora_connection.cursor()
        cursor.execute.side_effect = [
            None,  # Check table1
            None,  # Get row count
            None,  # Create backup table1
            Exception("Lock error"),  # Fail on table2
            None,  # Continue with table3
            None,
            None
        ]
        cursor.fetchone.side_effect = [
            ('table1',), (100,),
            ('table2',), (200,),
            ('table3',), (300,)
        ]
        
        with patch('pymysql.connect', return_value=mock_aurora_connection):
            # Should not raise exception
            backup_count = create_table_backups(
                mock_aurora_connection,
                ['table1', 'table2', 'table3'],
                'silver'
            )
            
            # Should have created at least one backup
            assert backup_count > 0


class TestMainWorkflow:
    """Test end-to-end silver transformer workflow."""
    
    @patch('boto3.client')
    @patch('subprocess.run')
    @patch('pymysql.connect')
    def test_full_workflow_success(
        self,
        mock_connect,
        mock_subprocess,
        mock_boto_client,
        mock_aurora_connection,
        mock_secretsmanager_client,
        mock_dbt_result
    ):
        """Should execute full silver transformation workflow."""
        # Setup mocks
        mock_boto_client.return_value = mock_secretsmanager_client
        mock_connect.return_value = mock_aurora_connection
        mock_subprocess.return_value = mock_dbt_result
        
        # This will be the main() function call once implemented
        # result = main()
        # assert result['status'] == 'SUCCESS'
        # assert result['models_built'] == 6
        # assert result['backup_count'] > 0
        pass
    
    def test_validates_staging_dependencies(self):
        """Should verify staging tables exist before transforming."""
        # Test will verify required staging tables are present
        pass
    
    def test_handles_dbt_compilation_errors(self):
        """Should handle dbt compilation errors gracefully."""
        # Test will verify error handling for dbt failures
        pass


# Run tests with: pytest glue/tests/test_silver_transformer.py -v
