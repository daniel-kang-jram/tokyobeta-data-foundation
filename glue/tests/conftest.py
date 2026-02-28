"""
pytest configuration and fixtures for Glue script testing.
Sets up proper mocking for AWS Glue dependencies.
"""

import os
import sys
from pathlib import Path
import pytest
from unittest.mock import Mock, MagicMock

# GitHub Actions runners may not have an AWS region configured, but several Glue scripts
# create boto3 clients at import time. Ensure a default region exists before imports.
os.environ.setdefault('AWS_REGION', 'ap-northeast-1')
os.environ.setdefault('AWS_DEFAULT_REGION', 'ap-northeast-1')

# Mock AWS Glue modules BEFORE any imports
mock_args = {
    'JOB_NAME': 'test-job',
    'S3_SOURCE_BUCKET': 'test-bucket',
    'S3_SOURCE_PREFIX': 'dumps/',
    'AURORA_ENDPOINT': 'test.cluster.amazonaws.com',
    'AURORA_DATABASE': 'test',
    'AURORA_SECRET_ARN': 'arn:aws:secretsmanager:us-east-1:123456789012:secret:test',
    'ENVIRONMENT': 'test',
}

# Mock getResolvedOptions to return test args
mock_get_resolved_options = Mock(return_value=mock_args)

# Mock Glue modules
mock_glue_utils = Mock()
mock_glue_utils.getResolvedOptions = mock_get_resolved_options

mock_glue_context = Mock()
mock_glue_job = Mock()

mock_spark_context = Mock()
mock_spark_context.return_value = Mock()

sys.modules['awsglue'] = Mock()
sys.modules['awsglue.utils'] = mock_glue_utils
sys.modules['awsglue.context'] = mock_glue_context
sys.modules['awsglue.job'] = mock_glue_job
sys.modules['pyspark'] = Mock()
sys.modules['pyspark.context'] = mock_spark_context

# pymysql depends on the cryptography library which can panic at import time when
# pip-installed and system versions conflict.  Pre-stub the package so all glue
# scripts can be collected regardless of driver availability.  Tests that need
# pymysql behaviour pass Mock connections/cursors directly into the functions
# under test, so the real driver is never needed during unit testing.
if 'pymysql' not in sys.modules:
    _mock_pymysql = Mock()
    # Real sentinel classes are required so that Mock(spec=pymysql.Connection) /
    # Mock(spec=pymysql.cursors.Cursor) don't raise InvalidSpecError.
    # The classes must declare the methods that tests access through the spec-mock.
    class _Connection:
        def cursor(self): ...
        def commit(self): ...
        def rollback(self): ...
        def close(self): ...

    class _Cursor:
        def execute(self, query, args=None): ...
        def executemany(self, query, args=None): ...
        def fetchone(self): ...
        def fetchall(self): ...
        def fetchmany(self, size=None): ...
        def close(self): ...
        def __enter__(self): ...
        def __exit__(self, *a): ...

    _mock_pymysql.Connection = _Connection
    _mock_pymysql.cursors = Mock()
    _mock_pymysql.cursors.Cursor = _Cursor
    _mock_pymysql.cursors.DictCursor = type("DictCursor", (_Cursor,), {})
    sys.modules['pymysql'] = _mock_pymysql
    sys.modules['pymysql.cursors'] = _mock_pymysql.cursors

# Add repo root + scripts directory to path (must be portable across CI runners)
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / 'glue' / 'scripts'))


@pytest.fixture
def mock_dbt_result():
    """Standard dbt subprocess result used across transformer tests."""
    result = MagicMock()
    result.returncode = 0
    result.stdout = 'Completed successfully'
    result.stderr = ''
    return result


@pytest.fixture
def mock_secretsmanager_client():
    """Mock Secrets Manager client returning username/password payload."""
    client = Mock()
    client.get_secret_value.return_value = {
        'SecretString': '{"username": "test_user", "password": "test_pass"}'
    }
    return client


@pytest.fixture
def mock_aurora_connection():
    """Mock Aurora connection object with cursor for DB mutation tests."""
    connection = Mock()
    cursor = Mock()
    connection.cursor.return_value = cursor
    return connection
