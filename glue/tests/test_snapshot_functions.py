"""
Tests for daily ETL snapshot export/load functions

Tests the daily snapshot export to S3 and loading from S3 back into Aurora.
"""

import pytest
import boto3
import pymysql
from unittest.mock import Mock, patch, MagicMock
from datetime import date, datetime
from io import BytesIO, StringIO
import csv


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
def sample_tenant_data():
    """Sample tenant data for testing."""
    return [
        (1, 9, 1, 'Tanaka Taro'),
        (2, 15, 1, 'Suzuki Hanako'),
        (3, 9, 2, 'Toyota Corp'),
        (4, 11, 1, 'Yamada Ichiro')
    ]


class TestSnapshotExport:
    """Test exporting daily tenant snapshots to S3."""
    
    def test_query_current_tenant_snapshot(self, mock_aurora_connection, sample_tenant_data):
        """Test querying current tenant status from staging.tenants."""
        from daily_etl import query_tenant_snapshot
        
        conn, cursor = mock_aurora_connection
        cursor.fetchall.return_value = sample_tenant_data
        
        rows = query_tenant_snapshot(cursor)
        
        assert len(rows) == 4
        assert rows[0] == (1, 9, 1, 'Tanaka Taro')
        
        # Verify query structure
        cursor.execute.assert_called_once()
        query = cursor.execute.call_args[0][0]
        assert 'SELECT id, status, contract_type, full_name' in query
        assert 'FROM staging.tenants' in query
    
    def test_generate_snapshot_csv(self, sample_tenant_data):
        """Test generating CSV from snapshot data."""
        from daily_etl import generate_snapshot_csv
        
        snapshot_date = date(2026, 2, 7)
        csv_content = generate_snapshot_csv(sample_tenant_data, snapshot_date)
        
        # Parse CSV and verify
        reader = csv.DictReader(StringIO(csv_content))
        rows = list(reader)
        
        assert len(rows) == 4
        assert rows[0]['tenant_id'] == '1'
        assert rows[0]['status'] == '9'
        assert rows[0]['contract_type'] == '1'
        assert rows[0]['full_name'] == 'Tanaka Taro'
        assert rows[0]['snapshot_date'] == '2026-02-07'
    
    def test_upload_snapshot_csv_to_s3(self, mock_s3_client):
        """Test uploading snapshot CSV to S3."""
        from daily_etl import upload_snapshot_csv
        
        csv_content = "tenant_id,status,contract_type,full_name,snapshot_date\n1,9,1,Test,2026-02-07\n"
        snapshot_date = date(2026, 2, 7)
        
        upload_snapshot_csv(
            mock_s3_client,
            'jram-gghouse',
            csv_content,
            snapshot_date
        )
        
        # Verify S3 put_object was called correctly
        mock_s3_client.put_object.assert_called_once()
        call_args = mock_s3_client.put_object.call_args[1]
        
        assert call_args['Bucket'] == 'jram-gghouse'
        assert 'snapshots/tenant_status/20260207.csv' in call_args['Key']
        assert call_args['Body'] == csv_content.encode('utf-8')
        assert call_args['ContentType'] == 'text/csv'
    
    def test_export_tenant_snapshot_end_to_end(self, mock_aurora_connection, mock_s3_client, sample_tenant_data):
        """Test complete snapshot export workflow."""
        from daily_etl import export_tenant_snapshot_to_s3
        
        conn, cursor = mock_aurora_connection
        cursor.fetchall.return_value = sample_tenant_data
        
        result = export_tenant_snapshot_to_s3(
            conn,
            mock_s3_client,
            'jram-gghouse',
            date(2026, 2, 7)
        )
        
        assert result['status'] == 'success'
        assert result['rows_exported'] == 4
        assert result['snapshot_date'] == date(2026, 2, 7)
        
        # Verify S3 upload occurred
        mock_s3_client.put_object.assert_called_once()


class TestSnapshotLoad:
    """Test loading historical snapshots from S3 into Aurora."""
    
    def test_list_snapshot_csvs_from_s3(self, mock_s3_client):
        """Test listing all snapshot CSV files from S3."""
        from daily_etl import list_snapshot_csvs
        
        # Mock S3 response
        mock_s3_client.list_objects_v2.return_value = {
            'Contents': [
                {'Key': 'snapshots/tenant_status/20260101.csv', 'LastModified': datetime(2026, 1, 1)},
                {'Key': 'snapshots/tenant_status/20260102.csv', 'LastModified': datetime(2026, 1, 2)},
                {'Key': 'snapshots/tenant_status/20260103.csv', 'LastModified': datetime(2026, 1, 3)},
            ]
        }
        
        csv_keys = list_snapshot_csvs(mock_s3_client, 'jram-gghouse')
        
        assert len(csv_keys) == 3
        assert csv_keys[0] == 'snapshots/tenant_status/20260101.csv'
        mock_s3_client.list_objects_v2.assert_called_once()
    
    def test_create_tenant_daily_snapshots_table(self, mock_aurora_connection):
        """Test creating staging.tenant_daily_snapshots table."""
        from daily_etl import create_tenant_daily_snapshots_table
        
        conn, cursor = mock_aurora_connection
        
        create_tenant_daily_snapshots_table(cursor)
        
        # Verify CREATE TABLE was called
        cursor.execute.assert_called()
        create_stmt = cursor.execute.call_args[0][0]
        assert 'CREATE TABLE IF NOT EXISTS' in create_stmt
        assert 'tenant_daily_snapshots' in create_stmt
        assert 'tenant_id' in create_stmt
        assert 'status' in create_stmt
        assert 'snapshot_date' in create_stmt
    
    def test_download_and_parse_csv(self, mock_s3_client):
        """Test downloading and parsing a snapshot CSV from S3."""
        from daily_etl import download_and_parse_csv
        
        csv_content = """tenant_id,status,contract_type,full_name,snapshot_date
1,9,1,Tanaka Taro,2026-01-01
2,15,1,Suzuki Hanako,2026-01-01
3,9,2,Toyota Corp,2026-01-01
"""
        
        mock_s3_client.get_object.return_value = {
            'Body': BytesIO(csv_content.encode('utf-8'))
        }
        
        rows = download_and_parse_csv(
            mock_s3_client,
            'jram-gghouse',
            'snapshots/tenant_status/20260101.csv'
        )
        
        assert len(rows) == 3
        assert rows[0] == (1, 9, 1, 'Tanaka Taro', date(2026, 1, 1))
        
        mock_s3_client.get_object.assert_called_once()
    
    def test_bulk_insert_snapshots(self, mock_aurora_connection):
        """Test bulk inserting snapshot rows into Aurora."""
        from daily_etl import bulk_insert_snapshots
        
        conn, cursor = mock_aurora_connection
        
        rows = [
            (1, 9, 1, 'Name1', date(2026, 1, 1)),
            (2, 15, 1, 'Name2', date(2026, 1, 1)),
            (3, 9, 2, 'Name3', date(2026, 1, 1))
        ]
        
        inserted = bulk_insert_snapshots(conn, cursor, rows)
        
        assert inserted == 3
        
        # Verify executemany was called
        cursor.executemany.assert_called_once()
        insert_query = cursor.executemany.call_args[0][0]
        assert 'INSERT INTO staging.tenant_daily_snapshots' in insert_query
        
        conn.commit.assert_called_once()
    
    def test_load_snapshots_with_batching(self, mock_aurora_connection, mock_s3_client):
        """Test loading multiple snapshot files with batching."""
        from daily_etl import load_tenant_snapshots_from_s3
        
        conn, cursor = mock_aurora_connection
        
        # Mock multiple CSV files
        mock_s3_client.list_objects_v2.return_value = {
            'Contents': [
                {'Key': f'snapshots/tenant_status/2026010{i}.csv'} for i in range(1, 4)
            ]
        }
        
        # Mock CSV content
        csv_content = "tenant_id,status,contract_type,full_name,snapshot_date\n1,9,1,Test,2026-01-01\n"
        mock_s3_client.get_object.return_value = {
            'Body': BytesIO(csv_content.encode('utf-8'))
        }
        
        result = load_tenant_snapshots_from_s3(
            conn,
            mock_s3_client,
            'jram-gghouse'
        )
        
        assert result['status'] == 'success'
        assert result['csv_files_loaded'] == 3
        assert result['total_rows_loaded'] == 3  # 1 row per CSV
        
        # Verify TRUNCATE was called
        cursor.execute.assert_any_call('TRUNCATE TABLE staging.tenant_daily_snapshots')
    
    def test_load_snapshots_error_handling(self, mock_aurora_connection, mock_s3_client):
        """Test error handling when loading snapshots."""
        from daily_etl import load_tenant_snapshots_from_s3
        
        conn, cursor = mock_aurora_connection
        
        mock_s3_client.list_objects_v2.return_value = {
            'Contents': [
                {'Key': 'snapshots/tenant_status/20260101.csv'},
                {'Key': 'snapshots/tenant_status/20260102.csv'}
            ]
        }
        
        # First CSV succeeds, second fails
        def side_effect(*args, **kwargs):
            key = kwargs.get('Key', args[1] if len(args) > 1 else '')
            if '20260102' in key:
                raise Exception("S3 download error")
            return {'Body': BytesIO(b"tenant_id,status,contract_type,full_name,snapshot_date\n1,9,1,Test,2026-01-01\n")}
        
        mock_s3_client.get_object.side_effect = side_effect
        
        result = load_tenant_snapshots_from_s3(
            conn,
            mock_s3_client,
            'jram-gghouse'
        )
        
        # Should continue despite errors
        assert result['csv_files_loaded'] == 1
        assert result['csv_files_failed'] == 1


class TestDataQuality:
    """Test data quality checks for snapshots."""
    
    def test_validate_snapshot_row_counts(self, mock_aurora_connection):
        """Test validating row counts after loading."""
        from daily_etl import validate_snapshot_counts
        
        conn, cursor = mock_aurora_connection
        
        # Mock count queries
        cursor.fetchone.return_value = (3500,)
        
        stats = validate_snapshot_counts(cursor)
        
        assert stats['total_rows'] == 3500
        assert stats['unique_tenants'] is not None
        assert stats['date_range'] is not None
        
        # Verify COUNT queries were executed
        assert cursor.execute.call_count >= 3
    
    def test_detect_missing_dates(self, mock_aurora_connection):
        """Test detecting missing snapshot dates."""
        from daily_etl import detect_missing_dates
        
        conn, cursor = mock_aurora_connection
        
        # Mock date list with a gap
        cursor.fetchall.return_value = [
            (date(2026, 1, 1),),
            (date(2026, 1, 2),),
            # Missing 2026-01-03
            (date(2026, 1, 4),),
            (date(2026, 1, 5),)
        ]
        
        missing = detect_missing_dates(cursor)
        
        assert date(2026, 1, 3) in missing
        assert len(missing) == 1
    
    def test_validate_no_future_dates(self, mock_aurora_connection):
        """Test validation that no snapshots have future dates."""
        from daily_etl import validate_no_future_dates
        
        conn, cursor = mock_aurora_connection
        
        # Mock query - should return 0 for valid data
        cursor.fetchone.return_value = (0,)
        
        is_valid = validate_no_future_dates(cursor)
        
        assert is_valid is True
        
        # Test with future dates present
        cursor.fetchone.return_value = (5,)
        
        is_valid = validate_no_future_dates(cursor)
        
        assert is_valid is False


class TestIncrementalLoading:
    """Test incremental snapshot loading strategies."""
    
    def test_load_only_new_snapshots(self, mock_aurora_connection, mock_s3_client):
        """Test loading only snapshots newer than max date in table."""
        from daily_etl import load_new_snapshots_only
        
        conn, cursor = mock_aurora_connection
        
        # Mock max date query
        cursor.fetchone.return_value = (date(2026, 1, 3),)
        
        # Mock S3 with multiple CSV files
        mock_s3_client.list_objects_v2.return_value = {
            'Contents': [
                {'Key': 'snapshots/tenant_status/20260101.csv'},
                {'Key': 'snapshots/tenant_status/20260102.csv'},
                {'Key': 'snapshots/tenant_status/20260103.csv'},
                {'Key': 'snapshots/tenant_status/20260104.csv'},  # New
                {'Key': 'snapshots/tenant_status/20260105.csv'},  # New
            ]
        }
        
        result = load_new_snapshots_only(
            conn,
            mock_s3_client,
            'jram-gghouse'
        )
        
        # Should only load files after 2026-01-03
        assert result['csv_files_loaded'] == 2
        assert result['skipped_existing'] == 3


class TestPerformance:
    """Test performance optimizations."""
    
    def test_batch_size_configuration(self):
        """Test that batch size can be configured."""
        from daily_etl import SnapshotLoader
        
        loader = SnapshotLoader(batch_size=500)
        
        assert loader.batch_size == 500
    
    def test_parallel_csv_downloads(self, mock_s3_client):
        """Test parallel downloading of CSV files."""
        from daily_etl import download_csvs_parallel
        
        csv_keys = [f'snapshots/tenant_status/2026010{i}.csv' for i in range(1, 6)]
        
        mock_s3_client.get_object.return_value = {
            'Body': BytesIO(b"tenant_id,status,contract_type,full_name,snapshot_date\n1,9,1,Test,2026-01-01\n")
        }
        
        results = download_csvs_parallel(
            mock_s3_client,
            'jram-gghouse',
            csv_keys,
            max_workers=3
        )
        
        assert len(results) == 5
        # Verify all downloads succeeded
        assert all(r['status'] == 'success' for r in results)
