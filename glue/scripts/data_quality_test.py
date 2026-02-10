"""
AWS Glue ETL Job: Data Quality Test Runner
Runs dbt tests for Silver and Gold layers after transformations complete.

This job runs:
1. After gold_transformer completes (daily pipeline)
2. Tests critical tables: gold.occupancy_daily_metrics, silver.tokyo_beta_tenant_room_info
3. Part of the daily quality assurance workflow
"""

import sys
import boto3
import json
import subprocess
import os
import re
from datetime import datetime
from awsglue.utils import getResolvedOptions
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.context import SparkContext

# Initialize Glue context
sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)

# Get job parameters
args = getResolvedOptions(sys.argv, [
    'JOB_NAME',
    'S3_SOURCE_BUCKET',
    'DBT_PROJECT_PATH',
    'AURORA_ENDPOINT',
    'AURORA_DATABASE',
    'AURORA_SECRET_ARN',
    'ENVIRONMENT'
])

job.init(args['JOB_NAME'], args)

# Initialize clients
s3 = boto3.client('s3')
secretsmanager = boto3.client('secretsmanager')


def get_aurora_credentials(secretsmanager_client, secret_arn):
    """Retrieve Aurora credentials from Secrets Manager."""
    response = secretsmanager_client.get_secret_value(SecretId=secret_arn)
    secret = json.loads(response['SecretString'])
    return secret['username'], secret['password']


def get_dbt_executable_path():
    """Get path to dbt executable in Glue environment."""
    possible_paths = [
        "/home/spark/.local/bin/dbt",
        "/usr/local/bin/dbt",
        "dbt"
    ]
    
    for path in possible_paths:
        if os.path.exists(path) or path == "dbt":
            return path
    
    return "dbt"


def download_dbt_project(bucket, s3_prefix, local_path):
    """Download dbt project from S3."""
    print(f"Downloading dbt project from s3://{bucket}/{s3_prefix}...")
    
    subprocess.run([
        "aws", "s3", "sync",
        f"s3://{bucket}/{s3_prefix}",
        local_path
    ], check=True)
    
    print(f"dbt project downloaded to {local_path}")
    return local_path


def install_dbt_dependencies(dbt_project_path):
    """Install dbt dependencies (dbt_utils, etc.)."""
    print("\nInstalling dbt dependencies...")
    
    dbt_executable = get_dbt_executable_path()
    
    result = subprocess.run([
        dbt_executable, "deps",
        "--profiles-dir", dbt_project_path,
        "--project-dir", dbt_project_path
    ], capture_output=True, text=True)
    
    print(result.stdout)
    if result.returncode != 0:
        print("=== DBT DEPS ERRORS ===")
        print(result.stderr)
        raise subprocess.CalledProcessError(
            result.returncode,
            result.args,
            result.stdout,
            result.stderr
        )
    
    return True


def run_dbt_tests(dbt_project_path, target_env, test_models):
    """
    Run dbt tests for specified models.
    
    Args:
        dbt_project_path: Path to dbt project
        target_env: Target environment (prod/dev)
        test_models: List of model names to test
        
    Returns:
        Result dict with test counts
    """
    print("\n" + "="*60)
    print("RUNNING DATA QUALITY TESTS")
    print(f"Models: {', '.join(test_models)}")
    print("="*60)
    
    dbt_executable = get_dbt_executable_path()
    
    # Build test command with explicit model selection
    cmd = [
        dbt_executable, "test",
        "--profiles-dir", dbt_project_path,
        "--project-dir", dbt_project_path,
        "--target", target_env,
        "--select"
    ] + test_models
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    print(result.stdout)
    
    # Parse test results
    tests_passed = 0
    tests_failed = 0
    
    if "passed" in result.stdout.lower():
        match = re.search(r'(\d+)\s+test.*passed', result.stdout, re.IGNORECASE)
        if match:
            tests_passed = int(match.group(1))
    
    if "failed" in result.stdout.lower() or result.returncode != 0:
        match = re.search(r'(\d+)\s+test.*failed', result.stdout, re.IGNORECASE)
        if match:
            tests_failed = int(match.group(1))
    
    if result.returncode != 0:
        print(f"WARNING: {tests_failed} tests failed")
    
    return {
        'tests_passed': tests_passed,
        'tests_failed': tests_failed,
        'output': result.stdout,
        'success': result.returncode == 0
    }


def main():
    """Main data quality test workflow."""
    start_time = datetime.now()
    
    try:
        print("="*60)
        print("DATA QUALITY TEST JOB STARTED")
        print(f"Environment: {args['ENVIRONMENT']}")
        print("="*60)
        
        # Step 1: Download dbt project from S3
        dbt_local_path = "/tmp/dbt-project"
        download_dbt_project(
            args['S3_SOURCE_BUCKET'],
            args['DBT_PROJECT_PATH'].replace(f"s3://{args['S3_SOURCE_BUCKET']}/", ""),
            dbt_local_path
        )
        
        # Step 2: Get database credentials
        username, password = get_aurora_credentials(secretsmanager, args['AURORA_SECRET_ARN'])
        
        # Set environment variables for dbt
        os.environ['AURORA_ENDPOINT'] = args['AURORA_ENDPOINT']
        os.environ['AURORA_USERNAME'] = username
        os.environ['AURORA_PASSWORD'] = password
        os.environ['DBT_TARGET'] = args['ENVIRONMENT']
        
        # Step 3: Install dbt dependencies
        install_dbt_dependencies(dbt_local_path)
        
        # Step 4: Run tests on critical tables
        # Focus on occupancy KPIs and tenant info (core business metrics)
        test_models = [
            "gold.occupancy_daily_metrics",
            "silver.tokyo_beta_tenant_room_info"
        ]
        
        test_result = run_dbt_tests(dbt_local_path, args['ENVIRONMENT'], test_models)
        
        # Calculate duration
        duration = (datetime.now() - start_time).total_seconds()
        
        # Log results
        result = {
            'status': 'SUCCESS' if test_result['success'] else 'TESTS_FAILED',
            'tests_passed': test_result['tests_passed'],
            'tests_failed': test_result['tests_failed'],
            'duration_seconds': int(duration)
        }
        
        print(f"\n{'='*60}")
        print("DATA QUALITY TEST JOB COMPLETED")
        print(f"Duration: {duration:.2f} seconds")
        print(f"Tests passed: {test_result['tests_passed']}")
        print(f"Tests failed: {test_result['tests_failed']}")
        print(f"{'='*60}\n")
        
        # Output result
        print(f"RESULT_JSON: {json.dumps(result)}")
        
        job.commit()
        return result
        
    except Exception as e:
        print(f"\nERROR: Data quality test job failed: {str(e)}")
        import traceback
        traceback.print_exc()
        
        result = {
            'status': 'FAILED',
            'error': str(e),
            'error_type': type(e).__name__
        }
        print(f"RESULT_JSON: {json.dumps(result)}")
        
        job.commit()
        raise


if __name__ == "__main__":
    main()
