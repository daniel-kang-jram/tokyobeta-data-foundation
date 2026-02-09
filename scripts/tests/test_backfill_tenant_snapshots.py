"""
Tests for backfill_tenant_snapshots.py

Tests the one-time backfill script that processes historical SQL dumps from S3
and extracts daily tenant status snapshots.
"""

import pytest
import boto3
import pymysql
from unittest.mock import Mock, patch, MagicMock, call
from datetime import date, datetime
from io import BytesIO
import csv


# Test fixtures
@pytest.fixture
def mock_s3_client():
    """Mock S3 client for testing."""
    client = Mock()
    return client


@pytest.fixture
def mock_aurora_connection():
    """Mock Aurora database connection."""
    conn = Mock(spec=pymysql.Connection)
    cursor = Mock(spec=pymysql.cursors.Cursor)
    conn.cursor.return_value = cursor
    cursor.__enter__ = Mock(return_value=cursor)
    cursor.__exit__ = Mock(return_value=False)
    return conn, cursor


@pytest.fixture
def mock_secrets_manager():
    """Mock Secrets Manager for Aurora credentials."""
    client = Mock()
    client.get_secret_value.return_value = {
        'SecretString': '{"username": "admin", "password": "test123"}'
    }
    return client


@pytest.fixture
def sample_dump_content():
    """Sample SQL dump content with tenants table."""
    return """
CREATE DATABASE IF NOT EXISTS `basis`;
USE `basis`;

CREATE TABLE `tenants` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `last_name` varchar(128) NOT NULL,
  `status` int unsigned NOT NULL,
  `contract_type` int unsigned NOT NULL,
  `full_name` varchar(191) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB;

INSERT INTO `tenants` VALUES (1,'Tanaka',9,1,'Tanaka Taro'),(2,'Suzuki',15,1,'Suzuki Hanako'),(3,'Toyota',9,2,'Toyota Corp');
"""


class TestDumpFileProcessing:
    """Test dump file download and parsing."""
    
    def test_list_dump_files_from_s3(self, mock_s3_client):
        """Test listing all dump files from S3."""
        from backfill_tenant_snapshots import list_dump_files
        
        # Mock S3 response
        mock_s3_client.list_objects_v2.return_value = {
            'Contents': [
                {'Key': 'dumps/gghouse_20251001.sql', 'LastModified': datetime(2025, 10, 1)},
                {'Key': 'dumps/gghouse_20251002.sql', 'LastModified': datetime(2025, 10, 2)},
                {'Key': 'dumps/processed/', 'LastModified': datetime(2025, 10, 1)},  # Should be filtered
            ]
        }
        
        files = list_dump_files(mock_s3_client, 'jram-gghouse', 'dumps/')
        
        assert len(files) == 2
        assert files[0] == 'dumps/gghouse_20251001.sql'
        assert files[1] == 'dumps/gghouse_20251002.sql'
        mock_s3_client.list_objects_v2.assert_called_once()
    
    def test_extract_date_from_filename(self):
        """Test extracting date from dump filename."""
        from backfill_tenant_snapshots import extract_date_from_filename
        
        assert extract_date_from_filename('dumps/gghouse_20251001.sql') == date(2025, 10, 1)
        assert extract_date_from_filename('dumps/gghouse_20251231.sql') == date(2025, 12, 31)
        
        with pytest.raises(ValueError):
            extract_date_from_filename('invalid_filename.sql')
    
    def test_download_tenants_section_from_s3(self, mock_s3_client):
        """Test downloading only the tenants section using byte range."""
        from backfill_tenant_snapshots import download_tenants_section
        
        sample_content = b"CREATE TABLE `tenants` (...); INSERT INTO `tenants` VALUES (...);"
        mock_s3_client.get_object.return_value = {
            'Body': BytesIO(sample_content),
            'ContentRange': 'bytes 760000000-860000000/900000000'
        }
        
        content = download_tenants_section(
            mock_s3_client,
            'jram-gghouse',
            'dumps/gghouse_20251001.sql'
        )
        
        assert sample_content in content
        mock_s3_client.get_object.assert_called_once()
        # Verify byte range was used
        call_args = mock_s3_client.get_object.call_args
        assert 'Range' in call_args[1]


class TestSQLStatementExtraction:
    """Test SQL statement parsing from dump content."""
    
    def test_extract_tenants_create_statement(self, sample_dump_content):
        """Test extracting CREATE TABLE statement for tenants."""
        from backfill_tenant_snapshots import extract_create_table_statement
        
        create_stmt = extract_create_table_statement(sample_dump_content, 'tenants')
        
        assert 'CREATE TABLE `tenants`' in create_stmt
        assert '`id` int unsigned' in create_stmt
        assert '`status` int unsigned' in create_stmt
        assert 'ENGINE=InnoDB' in create_stmt
    
    def test_extract_tenants_insert_statements(self, sample_dump_content):
        """Test extracting INSERT INTO statements for tenants."""
        from backfill_tenant_snapshots import extract_insert_statements
        
        insert_stmts = extract_insert_statements(sample_dump_content, 'tenants')
        
        assert len(insert_stmts) > 0
        assert 'INSERT INTO `tenants`' in insert_stmts[0]
        assert 'VALUES' in insert_stmts[0]
    
    def test_handle_multiline_insert_statements(self):
        """Test handling INSERT statements spanning multiple lines."""
        from backfill_tenant_snapshots import extract_insert_statements
        
        content = """
INSERT INTO `tenants` VALUES 
(1,'Name1',9,1,'Full1'),
(2,'Name2',15,2,'Full2'),
(3,'Name3',9,1,'Full3');
"""
        
        stmts = extract_insert_statements(content, 'tenants')
        assert len(stmts) == 1
        assert stmts[0].count('),(') == 2  # 3 rows = 2 separators


class TestAuroraDataLoading:
    """Test loading data into Aurora temp table."""
    
    def test_create_temp_table(self, mock_aurora_connection):
        """Test creating temporary table in Aurora."""
        from backfill_tenant_snapshots import create_temp_table
        
        conn, cursor = mock_aurora_connection
        create_stmt = "CREATE TABLE `_tmp_tenants` (`id` int, `status` int);"
        
        create_temp_table(cursor, create_stmt, '_tmp_tenants')
        
        # Should drop if exists, then create
        cursor.execute.assert_any_call("DROP TABLE IF EXISTS staging._tmp_tenants")
        cursor.execute.assert_any_call(create_stmt.replace('`tenants`', '`_tmp_tenants`'))
    
    def test_load_data_into_temp_table(self, mock_aurora_connection):
        """Test loading INSERT statements into temp table."""
        from backfill_tenant_snapshots import load_data_into_temp_table
        
        conn, cursor = mock_aurora_connection
        insert_stmts = [
            "INSERT INTO `tenants` VALUES (1,'A',9,1,'FullA'),(2,'B',15,2,'FullB');",
            "INSERT INTO `tenants` VALUES (3,'C',9,1,'FullC');"
        ]
        
        load_data_into_temp_table(conn, cursor, insert_stmts, '_tmp_tenants')
        
        # Should execute both statements (with table name replaced)
        assert cursor.execute.call_count >= 2
        conn.commit.assert_called_once()
    
    def test_extract_snapshot_from_temp_table(self, mock_aurora_connection):
        """Test extracting snapshot data from temp table."""
        from backfill_tenant_snapshots import extract_snapshot_from_temp_table
        
        conn, cursor = mock_aurora_connection
        cursor.fetchall.return_value = [
            (1, 9, 1, 'Tanaka Taro'),
            (2, 15, 1, 'Suzuki Hanako'),
            (3, 9, 2, 'Toyota Corp')
        ]
        
        snapshot_date = date(2025, 10, 1)
        rows = extract_snapshot_from_temp_table(cursor, '_tmp_tenants', snapshot_date)
        
        assert len(rows) == 3
        assert rows[0] == (1, 9, 1, 'Tanaka Taro', snapshot_date)
        
        # Verify query structure
        cursor.execute.assert_called_once()
        query = cursor.execute.call_args[0][0]
        assert 'SELECT id, status, contract_type, full_name' in query
        assert '_tmp_tenants' in query


class TestCSVExport:
    """Test CSV file generation and S3 upload."""
    
    def test_generate_csv_content(self):
        """Test generating CSV from snapshot rows."""
        from backfill_tenant_snapshots import generate_csv_content
        
        rows = [
            (1, 9, 1, 'Tanaka Taro', date(2025, 10, 1)),
            (2, 15, 1, 'Suzuki Hanako', date(2025, 10, 1)),
            (3, 9, 2, 'Toyota Corp', date(2025, 10, 1))
        ]
        
        csv_content = generate_csv_content(rows)
        
        # Parse CSV and verify
        lines = csv_content.strip().split('\n')
        assert len(lines) == 4  # Header + 3 data rows
        assert 'tenant_id,status,contract_type,full_name,snapshot_date' in lines[0]
        assert '1,9,1,Tanaka Taro,2025-10-01' in lines[1]
    
    def test_upload_snapshot_to_s3(self, mock_s3_client):
        """Test uploading snapshot CSV to S3."""
        from backfill_tenant_snapshots import upload_snapshot_to_s3
        
        csv_content = "tenant_id,status,contract_type,full_name,snapshot_date\n1,9,1,Test,2025-10-01\n"
        snapshot_date = date(2025, 10, 1)
        
        upload_snapshot_to_s3(
            mock_s3_client,
            'jram-gghouse',
            csv_content,
            snapshot_date
        )
        
        # Verify S3 put_object was called
        mock_s3_client.put_object.assert_called_once()
        call_args = mock_s3_client.put_object.call_args
        
        assert call_args[1]['Bucket'] == 'jram-gghouse'
        assert '20251001.csv' in call_args[1]['Key']
        assert call_args[1]['Body'] == csv_content.encode('utf-8')


class TestEndToEndWorkflow:
    """Test complete backfill workflow."""
    
    @patch('backfill_tenant_snapshots.boto3.client')
    @patch('backfill_tenant_snapshots.pymysql.connect')
    def test_process_single_dump_file(self, mock_connect, mock_boto_client, sample_dump_content):
        """Test processing a single dump file end-to-end."""
        from backfill_tenant_snapshots import process_dump_file
        
        # Setup mocks
        mock_s3 = Mock()
        mock_boto_client.return_value = mock_s3
        
        mock_s3.get_object.return_value = {
            'Body': BytesIO(sample_dump_content.encode('utf-8'))
        }
        
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=False)
        mock_connect.return_value = mock_conn
        
        mock_cursor.fetchall.return_value = [
            (1, 9, 1, 'Tanaka Taro'),
            (2, 15, 1, 'Suzuki Hanako')
        ]
        
        # Run processing
        result = process_dump_file(
            dump_key='dumps/gghouse_20251001.sql',
            bucket='jram-gghouse',
            aurora_endpoint='test.cluster.rds.amazonaws.com',
            aurora_database='tokyobeta',
            secret_arn='arn:aws:secretsmanager:...'
        )
        
        assert result['status'] == 'success'
        assert result['rows_processed'] == 2
        assert result['snapshot_date'] == date(2025, 10, 1)
    
    def test_backfill_with_error_handling(self, mock_s3_client, mock_aurora_connection):
        """Test that backfill continues on individual dump errors."""
        from backfill_tenant_snapshots import backfill_all_dumps
        
        conn, cursor = mock_aurora_connection
        
        # Simulate error on second dump
        def side_effect(bucket, key):
            if '20251002' in key:
                raise Exception("S3 download failed")
            return {'Body': BytesIO(b"test")}
        
        mock_s3_client.get_object.side_effect = side_effect
        
        dump_keys = ['dumps/gghouse_20251001.sql', 'dumps/gghouse_20251002.sql', 'dumps/gghouse_20251003.sql']
        
        results = backfill_all_dumps(
            mock_s3_client,
            conn,
            'jram-gghouse',
            dump_keys
        )
        
        # Should have 2 successes and 1 failure
        assert results['total_dumps'] == 3
        assert results['successful'] == 2
        assert results['failed'] == 1


class TestDataValidation:
    """Test data quality checks."""
    
    def test_validate_snapshot_data(self):
        """Test validation of extracted snapshot data."""
        from backfill_tenant_snapshots import validate_snapshot_data
        
        valid_rows = [
            (1, 9, 1, 'Name1', date(2025, 10, 1)),
            (2, 15, 2, 'Name2', date(2025, 10, 1))
        ]
        
        # Should not raise
        validate_snapshot_data(valid_rows)
        
        # Test invalid data - None tenant_id
        invalid_rows = [
            (None, 9, 1, 'Name1', date(2025, 10, 1))
        ]
        
        with pytest.raises(ValueError, match="tenant_id"):
            validate_snapshot_data(invalid_rows)
        
        # Test invalid data - None status
        invalid_rows = [
            (1, None, 1, 'Name1', date(2025, 10, 1))
        ]
        
        with pytest.raises(ValueError, match="status"):
            validate_snapshot_data(invalid_rows)
    
    def test_deduplicate_tenant_ids(self):
        """Test handling duplicate tenant IDs in same snapshot."""
        from backfill_tenant_snapshots import deduplicate_snapshots
        
        rows = [
            (1, 9, 1, 'Name1', date(2025, 10, 1)),
            (1, 15, 1, 'Name1_Updated', date(2025, 10, 1)),  # Duplicate ID
            (2, 9, 2, 'Name2', date(2025, 10, 1))
        ]
        
        deduplicated = deduplicate_snapshots(rows)
        
        # Should keep only the last occurrence of each tenant_id
        assert len(deduplicated) == 2
        tenant_ids = [r[0] for r in deduplicated]
        assert tenant_ids == [1, 2]
        # Should keep the updated status
        assert deduplicated[0][1] == 15


class TestProgressTracking:
    """Test progress reporting and resumability."""
    
    def test_track_progress(self, tmp_path):
        """Test progress tracking to enable resume."""
        from backfill_tenant_snapshots import ProgressTracker
        
        progress_file = tmp_path / "progress.json"
        tracker = ProgressTracker(str(progress_file))
        
        tracker.mark_complete('dumps/gghouse_20251001.sql', 28000)
        tracker.mark_complete('dumps/gghouse_20251002.sql', 28100)
        
        assert tracker.is_complete('dumps/gghouse_20251001.sql')
        assert not tracker.is_complete('dumps/gghouse_20251003.sql')
        
        # Test persistence
        tracker2 = ProgressTracker(str(progress_file))
        assert tracker2.is_complete('dumps/gghouse_20251001.sql')
    
    def test_skip_already_processed_dumps(self):
        """Test that backfill skips already processed dumps."""
        from backfill_tenant_snapshots import get_dumps_to_process
        
        all_dumps = [
            'dumps/gghouse_20251001.sql',
            'dumps/gghouse_20251002.sql',
            'dumps/gghouse_20251003.sql'
        ]
        
        completed = ['dumps/gghouse_20251001.sql']
        
        to_process = get_dumps_to_process(all_dumps, completed)
        
        assert len(to_process) == 2
        assert 'dumps/gghouse_20251001.sql' not in to_process
