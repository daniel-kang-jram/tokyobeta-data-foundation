"""
Unit tests for staging_loader.py
Following TDD (Test-Driven Development) principles:
- Tests written to document expected behavior
- Each function tested independently
- Mocks used for external dependencies (S3, Secrets Manager, MySQL)
"""

import pytest
import sys
from unittest.mock import Mock, MagicMock, patch, call
from datetime import datetime
import json

# Note: AWS Glue mocks configured in conftest.py

# Import functions to test
# conftest.py sets up all mocks and adds scripts to path
from staging_loader import (
    normalize_statement,
    extract_table_name,
    iter_sql_statements,
    get_latest_dump_key,
    get_aurora_credentials,
    download_dump_file,
    open_dump_file,
    parse_dump_file,
    load_to_aurora_staging,
    cleanup_empty_staging_tables,
    archive_processed_dump
)


class TestNormalizeStatement:
    """Test SQL statement normalization."""
    
    def test_removes_leading_trailing_whitespace(self):
        """Should strip whitespace from statement."""
        result = normalize_statement("  SELECT * FROM users;  ")
        assert result == "SELECT * FROM users;"
    
    def test_skips_set_commands(self):
        """Should skip SET commands (session-level)."""
        assert normalize_statement("SET NAMES utf8;") == ""
        assert normalize_statement("set autocommit=1;") == ""
    
    def test_skips_lock_commands(self):
        """Should skip LOCK/UNLOCK TABLE commands."""
        assert normalize_statement("LOCK TABLES users WRITE;") == ""
        assert normalize_statement("UNLOCK TABLES;") == ""
    
    def test_skips_create_database(self):
        """Should skip CREATE DATABASE commands."""
        assert normalize_statement("CREATE DATABASE test;") == ""
    
    def test_skips_use_database(self):
        """Should skip USE commands."""
        assert normalize_statement("USE staging;") == ""
    
    def test_preserves_valid_statements(self):
        """Should preserve valid SQL statements."""
        stmt = "CREATE TABLE users (id INT, name VARCHAR(100));"
        assert normalize_statement(stmt) == stmt
        
        stmt = "INSERT INTO users VALUES (1, 'John');"
        assert normalize_statement(stmt) == stmt
    
    def test_empty_statement_returns_empty(self):
        """Should return empty string for empty input."""
        assert normalize_statement("") == ""
        assert normalize_statement("   ") == ""


class TestExtractTableName:
    """Test table name extraction from SQL."""
    
    def test_extracts_from_create_table(self):
        """Should extract table name from CREATE TABLE."""
        stmt = "CREATE TABLE users (id INT);"
        assert extract_table_name(stmt) == "users"
        
        stmt = "CREATE TABLE `tenant_data` (id INT);"
        assert extract_table_name(stmt) == "tenant_data"
    
    def test_extracts_from_insert(self):
        """Should extract table name from INSERT INTO."""
        stmt = "INSERT INTO users VALUES (1, 'test');"
        assert extract_table_name(stmt) == "users"
    
    def test_extracts_from_drop_table(self):
        """Should extract table name from DROP TABLE."""
        stmt = "DROP TABLE IF EXISTS users;"
        assert extract_table_name(stmt) == "users"
        
        stmt = "DROP TABLE users;"
        assert extract_table_name(stmt) == "users"
    
    def test_returns_none_for_non_table_statements(self):
        """Should return None for non-table statements."""
        assert extract_table_name("SELECT * FROM users;") is None
        assert extract_table_name("SET NAMES utf8;") is None


class TestIterSqlStatements:
    """Test SQL statement iteration."""
    
    def test_yields_single_statement(self):
        """Should yield single complete statement."""
        lines = ["SELECT * FROM users;"]
        result = list(iter_sql_statements(lines))
        assert len(result) == 1
        assert result[0] == "SELECT * FROM users;"
    
    def test_yields_multiline_statement(self):
        """Should handle statements spanning multiple lines."""
        lines = [
            "CREATE TABLE users (\n",
            "  id INT,\n",
            "  name VARCHAR(100)\n",
            ");\n"
        ]
        result = list(iter_sql_statements(lines))
        assert len(result) == 1
        assert "CREATE TABLE users" in result[0]
        assert "name VARCHAR(100)" in result[0]
    
    def test_skips_single_line_comments(self):
        """Should skip -- comments."""
        lines = [
            "-- This is a comment\n",
            "SELECT * FROM users;\n"
        ]
        result = list(iter_sql_statements(lines))
        assert len(result) == 1
        assert result[0] == "SELECT * FROM users;"
    
    def test_skips_block_comments(self):
        """Should skip /* */ block comments."""
        lines = [
            "/* Multi-line\n",
            "   comment */\n",
            "SELECT * FROM users;\n"
        ]
        result = list(iter_sql_statements(lines))
        assert len(result) == 1
        assert result[0] == "SELECT * FROM users;"
    
    def test_handles_multiple_statements(self):
        """Should yield multiple statements."""
        lines = [
            "CREATE TABLE users (id INT);\n",
            "INSERT INTO users VALUES (1);\n",
            "INSERT INTO users VALUES (2);\n"
        ]
        result = list(iter_sql_statements(lines))
        assert len(result) == 3
    
    def test_handles_set_commands_via_normalize(self):
        """Should filter out SET commands via normalize_statement."""
        lines = [
            "SET NAMES utf8;\n",
            "SELECT * FROM users;\n"
        ]
        result = list(iter_sql_statements(lines))
        # Only the SELECT should be yielded (SET filtered by normalize_statement)
        assert len(result) == 1
        assert result[0] == "SELECT * FROM users;"


class TestGetLatestDumpKey:
    """Test S3 dump file discovery."""
    
    def test_returns_latest_dump_by_modified_date(self):
        """Should return most recently modified dump."""
        mock_s3 = Mock()
        mock_s3.list_objects_v2.return_value = {
            'Contents': [
                {'Key': 'dumps/gghouse_20260205.sql', 'LastModified': datetime(2026, 2, 5)},
                {'Key': 'dumps/gghouse_20260207.sql', 'LastModified': datetime(2026, 2, 7)},
                {'Key': 'dumps/gghouse_20260206.sql', 'LastModified': datetime(2026, 2, 6)},
            ]
        }
        
        result = get_latest_dump_key(mock_s3, 'test-bucket', 'dumps/')
        assert result == 'dumps/gghouse_20260207.sql'
    
    def test_handles_gzipped_files(self):
        """Should handle .sql.gz files."""
        mock_s3 = Mock()
        mock_s3.list_objects_v2.return_value = {
            'Contents': [
                {'Key': 'dumps/gghouse_20260207.sql.gz', 'LastModified': datetime(2026, 2, 7)},
            ]
        }
        
        result = get_latest_dump_key(mock_s3, 'test-bucket', 'dumps/')
        assert result == 'dumps/gghouse_20260207.sql.gz'
    
    def test_raises_error_when_no_files(self):
        """Should raise ValueError when no files found."""
        mock_s3 = Mock()
        mock_s3.list_objects_v2.return_value = {}
        
        with pytest.raises(ValueError, match="No files found"):
            get_latest_dump_key(mock_s3, 'test-bucket', 'dumps/')
    
    def test_raises_error_when_no_matching_pattern(self):
        """Should raise ValueError when no files match pattern."""
        mock_s3 = Mock()
        mock_s3.list_objects_v2.return_value = {
            'Contents': [
                {'Key': 'dumps/other_file.sql', 'LastModified': datetime(2026, 2, 7)},
            ]
        }
        
        with pytest.raises(ValueError, match="No SQL dump files matching pattern"):
            get_latest_dump_key(mock_s3, 'test-bucket', 'dumps/')


class TestGetAuroraCredentials:
    """Test Secrets Manager credential retrieval."""
    
    def test_returns_username_and_password(self):
        """Should parse and return credentials."""
        mock_sm = Mock()
        mock_sm.get_secret_value.return_value = {
            'SecretString': json.dumps({
                'username': 'admin',
                'password': 'test-password-123'
            })
        }
        
        username, password = get_aurora_credentials(mock_sm, 'secret-arn')
        
        assert username == 'admin'
        assert password == 'test-password-123'
        mock_sm.get_secret_value.assert_called_once_with(SecretId='secret-arn')


class TestDownloadDumpFile:
    """Test S3 file download."""
    
    def test_downloads_to_tmp(self):
        """Should download file to /tmp directory."""
        mock_s3 = Mock()
        
        result = download_dump_file(mock_s3, 'test-bucket', 'dumps/gghouse_20260207.sql')
        
        assert result == '/tmp/gghouse_20260207.sql'
        mock_s3.download_file.assert_called_once_with(
            'test-bucket',
            'dumps/gghouse_20260207.sql',
            '/tmp/gghouse_20260207.sql'
        )


class TestLoadToAuroraStaging:
    """Test loading statements into Aurora."""
    
    def test_creates_required_schemas(self):
        """Should create staging, analytics, seeds schemas."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []
        
        statements = ["CREATE TABLE test (id INT);"]
        load_to_aurora_staging(mock_conn, statements)
        
        # Verify schema creation calls
        create_calls = [call for call in mock_cursor.execute.call_args_list 
                       if 'CREATE SCHEMA' in str(call)]
        assert len(create_calls) >= 3  # staging, analytics, seeds
    
    def test_executes_all_statements(self):
        """Should execute all provided statements."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []
        
        statements = [
            "CREATE TABLE test (id INT);",
            "INSERT INTO test VALUES (1);",
            "INSERT INTO test VALUES (2);"
        ]
        
        table_count, stmt_count = load_to_aurora_staging(mock_conn, statements)
        
        assert stmt_count == 3
    
    def test_commits_every_100_statements(self):
        """Should commit in batches of 100."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []
        
        statements = [f"INSERT INTO test VALUES ({i});" for i in range(250)]
        
        load_to_aurora_staging(mock_conn, statements)
        
        # Should commit at: 100, 200, and final
        assert mock_conn.commit.call_count >= 3
    
    def test_continues_on_statement_error(self):
        """Should continue processing even if individual statement fails."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []
        
        # Make second statement fail
        def side_effect(stmt):
            if "INSERT INTO test VALUES (2)" in stmt:
                raise Exception("Duplicate key error")
        
        mock_cursor.execute.side_effect = side_effect
        
        statements = [
            "INSERT INTO test VALUES (1);",
            "INSERT INTO test VALUES (2);",
            "INSERT INTO test VALUES (3);"
        ]
        
        # Should not raise, should continue
        table_count, stmt_count = load_to_aurora_staging(mock_conn, statements)
        assert stmt_count == 2  # Only 2 successful


class TestCleanupEmptyStagingTables:
    """Test empty table cleanup."""
    
    def test_drops_empty_tables(self):
        """Should drop tables with 0 rows."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        
        # Mock empty tables discovery
        mock_cursor.fetchall.return_value = [('empty_table1',), ('empty_table2',)]
        mock_cursor.fetchone.return_value = (0,)  # COUNT(*) returns 0
        
        dropped_count = cleanup_empty_staging_tables(mock_conn)
        
        assert dropped_count == 2
        # Verify DROP TABLE was called
        drop_calls = [call for call in mock_cursor.execute.call_args_list
                     if 'DROP TABLE' in str(call)]
        assert len(drop_calls) == 2
    
    def test_skips_non_empty_tables(self):
        """Should not drop tables with data."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        
        # Mock table reported as empty by metadata
        mock_cursor.fetchall.return_value = [('table1',)]
        # But COUNT(*) shows it has rows
        mock_cursor.fetchone.return_value = (100,)
        
        dropped_count = cleanup_empty_staging_tables(mock_conn)
        
        assert dropped_count == 0
        # Verify DROP TABLE was NOT called
        drop_calls = [call for call in mock_cursor.execute.call_args_list
                     if 'DROP TABLE' in str(call)]
        assert len(drop_calls) == 0
    
    def test_returns_zero_when_no_empty_tables(self):
        """Should return 0 when no empty tables found."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []
        
        dropped_count = cleanup_empty_staging_tables(mock_conn)
        
        assert dropped_count == 0


class TestArchiveProcessedDump:
    """Test dump file archiving."""
    
    def test_copies_to_processed_folder(self):
        """Should copy dump from dumps/ to processed/."""
        mock_s3 = Mock()
        
        archive_processed_dump(mock_s3, 'test-bucket', 'dumps/gghouse_20260207.sql')
        
        mock_s3.copy_object.assert_called_once()
        call_args = mock_s3.copy_object.call_args[1]  # Get kwargs
        
        # Verify destination key is in processed folder
        assert call_args['Key'] == 'processed/gghouse_20260207.sql'
        # Verify source is from dumps folder
        assert call_args['CopySource']['Key'] == 'dumps/gghouse_20260207.sql'
        assert call_args['Bucket'] == 'test-bucket'


# Test fixtures
@pytest.fixture
def sample_sql_lines():
    """Fixture providing sample SQL dump lines."""
    return [
        "-- MySQL dump 10.13\n",
        "SET NAMES utf8mb4;\n",
        "CREATE TABLE users (\n",
        "  id INT NOT NULL,\n",
        "  name VARCHAR(100)\n",
        ");\n",
        "INSERT INTO users VALUES (1, 'Alice');\n",
        "INSERT INTO users VALUES (2, 'Bob');\n",
    ]


@pytest.fixture
def mock_aurora_connection():
    """Fixture providing mocked Aurora connection."""
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value = cursor
    cursor.fetchall.return_value = []
    return conn


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
