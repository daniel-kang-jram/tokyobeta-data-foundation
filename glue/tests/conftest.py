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
