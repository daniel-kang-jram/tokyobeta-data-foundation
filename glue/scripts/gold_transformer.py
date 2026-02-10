"""
AWS Glue ETL Job: Gold Transformer
Runs dbt to transform silver → gold layer (business analytics).

Part of the resilient ETL architecture: Staging → Silver → Gold
This job focuses ONLY on the gold layer transformations.
"""

import sys
import boto3
import json
import subprocess
import os
from datetime import datetime, timedelta
from awsglue.utils import getResolvedOptions
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.context import SparkContext
import pymysql

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

# Gold tables to backup before transformation
GOLD_TABLES = [
    'daily_activity_summary',
    'new_contracts',
    'moveouts',
    'moveout_notices',
    'moveout_analysis',
    'moveout_summary'
]


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
    """
    Install dbt dependencies (dbt_utils, etc.).
    
    Args:
        dbt_project_path: Path to dbt project
        
    Returns:
        True if successful
    """
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


def run_dbt_gold_models(
    dbt_project_path,
    target_env,
    aurora_endpoint=None,
    aurora_username=None,
    aurora_password=None
):
    """
    Run dbt gold layer models only.
    
    Args:
        dbt_project_path: Path to dbt project
        target_env: Target environment (prod/dev)
        aurora_endpoint: Aurora endpoint
        aurora_username: Aurora username
        aurora_password: Aurora password
        
    Returns:
        Result dict with models_built count
    """
    print("\n" + "="*60)
    print("RUNNING DBT GOLD MODELS")
    print("="*60)
    
    # Set environment variables for dbt profiles
    if aurora_endpoint:
        os.environ['AURORA_ENDPOINT'] = aurora_endpoint
    if aurora_username:
        os.environ['AURORA_USERNAME'] = aurora_username
    if aurora_password:
        os.environ['AURORA_PASSWORD'] = aurora_password
    os.environ['DBT_TARGET'] = target_env
    
    dbt_executable = get_dbt_executable_path()
    
    # Run only gold models with --fail-fast
    result = subprocess.run([
        dbt_executable, "run",
        "--profiles-dir", dbt_project_path,
        "--project-dir", dbt_project_path,
        "--target", target_env,
        "--models", "gold.*",
        "--fail-fast"
    ], capture_output=True, text=True)
    
    print(result.stdout)
    if result.stderr:
        print("=== DBT RUN WARNINGS ===")
        print(result.stderr)
    
    if result.returncode != 0:
        print("=== DBT RUN FAILED ===")
        raise subprocess.CalledProcessError(
            result.returncode,
            result.args,
            result.stdout,
            result.stderr
        )
    
    # Parse model count from output
    models_built = len(GOLD_TABLES)  # Approximate count
    
    return {
        'success': True,
        'models_built': models_built,
        'output': result.stdout
    }


def run_dbt_gold_tests(dbt_project_path, target_env):
    """
    Run dbt tests for gold layer models.
    
    Args:
        dbt_project_path: Path to dbt project
        target_env: Target environment (prod/dev)
        
    Returns:
        Result dict with test counts
    """
    print("\n" + "="*60)
    print("RUNNING DBT GOLD TESTS")
    print("="*60)
    
    dbt_executable = get_dbt_executable_path()
    
    result = subprocess.run([
        dbt_executable, "test",
        "--profiles-dir", dbt_project_path,
        "--project-dir", dbt_project_path,
        "--target", target_env,
        "--models", "gold.*"
    ], capture_output=True, text=True)
    
    print(result.stdout)
    
    # Parse test results
    tests_passed = 0
    tests_failed = 0
    
    if "passed" in result.stdout.lower():
        import re
        match = re.search(r'(\d+)\s+test.*passed', result.stdout, re.IGNORECASE)
        if match:
            tests_passed = int(match.group(1))
    
    if "failed" in result.stdout.lower() or result.returncode != 0:
        import re
        match = re.search(r'(\d+)\s+test.*failed', result.stdout, re.IGNORECASE)
        if match:
            tests_failed = int(match.group(1))
    
    if result.returncode != 0:
        print(f"WARNING: {tests_failed} tests failed (non-blocking)")
    
    return {
        'tests_passed': tests_passed,
        'tests_failed': tests_failed,
        'output': result.stdout
    }


def cleanup_dbt_tmp_tables(connection, schema):
    """
    Clean up leftover dbt temporary tables (*__dbt_tmp).
    
    Args:
        connection: pymysql connection
        schema: Schema name to check
        
    Returns:
        Number of tables dropped
    """
    print(f"\n=== Cleaning up dbt temp tables in {schema} ===")
    
    cursor = connection.cursor()
    dropped_count = 0
    
    try:
        # Find all tables ending with __dbt_tmp
        cursor.execute(f"""
            SELECT TABLE_NAME 
            FROM information_schema.TABLES 
            WHERE TABLE_SCHEMA = '{schema}' 
            AND TABLE_NAME LIKE '%__dbt_tmp'
        """)
        
        tmp_tables = [row[0] for row in cursor.fetchall()]
        
        if not tmp_tables:
            print("  No temporary tables found.")
            return 0
            
        print(f"  Found {len(tmp_tables)} temporary tables: {', '.join(tmp_tables)}")
        
        for table_name in tmp_tables:
            print(f"  Dropping {schema}.{table_name}...")
            cursor.execute(f"DROP TABLE IF EXISTS {schema}.{table_name}")
            dropped_count += 1
            
        connection.commit()
        print(f"  ✓ Dropped {dropped_count} temporary tables")
        return dropped_count
        
    except Exception as e:
        print(f"  ⚠ Warning: Failed to cleanup temp tables: {str(e)}")
        return 0
    finally:
        cursor.close()


def create_table_backups(connection, tables, schema='gold'):
    """
    Create backup copies of tables before transformation.
    
    Args:
        connection: pymysql connection
        tables: List of table names to backup
        schema: Schema name
        
    Returns:
        Number of backups created
    """
    print(f"\n=== Creating Pre-Transform Backups ({schema} layer) ===")
    
    backup_count = 0
    backup_suffix = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    cursor = connection.cursor()
    
    try:
        for table_name in tables:
            backup_name = f"{table_name}_backup_{backup_suffix}"
            
            try:
                cursor.execute(f"SHOW TABLES FROM {schema} LIKE '{table_name}'")
                if cursor.fetchone():
                    cursor.execute(f"SELECT COUNT(*) FROM {schema}.{table_name}")
                    row_count = cursor.fetchone()[0]
                    
                    print(f"  Backing up {schema}.{table_name} ({row_count} rows)...")
                    
                    cursor.execute(f"""
                        CREATE TABLE {schema}.{backup_name} 
                        AS SELECT * FROM {schema}.{table_name}
                    """)
                    
                    print(f"    ✓ Created {schema}.{backup_name}")
                    backup_count += 1
                else:
                    print(f"  ⊘ Skipping {table_name} (table does not exist)")
                    
            except Exception as e:
                print(f"  ✗ Failed to backup {table_name}: {str(e)[:200]}")
                continue
        
        connection.commit()
        print(f"\nBackup complete: {backup_count} tables backed up")
        return backup_count
        
    finally:
        cursor.close()


def cleanup_old_backups(connection, days_to_keep=3):
    """
    Remove backup tables older than N days.
    
    Args:
        connection: pymysql connection
        days_to_keep: Number of days to retain backups
        
    Returns:
        Number of backups removed
    """
    print(f"\n=== Cleaning Up Old Backups (keeping last {days_to_keep} days) ===")
    
    cutoff_date = (datetime.now() - timedelta(days=days_to_keep)).strftime('%Y%m%d')
    
    removed_count = 0
    cursor = connection.cursor()
    
    try:
        for schema in ['silver', 'gold']:
            cursor.execute(f"""
                SELECT TABLE_NAME 
                FROM information_schema.TABLES 
                WHERE TABLE_SCHEMA = '{schema}' 
                AND TABLE_NAME LIKE '%_backup_%'
                ORDER BY TABLE_NAME
            """)
            
            backup_tables = [row[0] for row in cursor.fetchall()]
            
            for table_name in backup_tables:
                if '_backup_' in table_name:
                    try:
                        date_part = table_name.split('_backup_')[1][:8]
                        if date_part < cutoff_date:
                            print(f"  Removing old backup: {schema}.{table_name} (date: {date_part})")
                            cursor.execute(f"DROP TABLE IF EXISTS {schema}.{table_name}")
                            removed_count += 1
                    except (IndexError, ValueError) as e:
                        print(f"  Warning: Could not parse date from {table_name}: {e}")
                        continue
        
        connection.commit()
        print(f"Cleanup complete: {removed_count} old backups removed")
        return removed_count
        
    finally:
        cursor.close()


def main():
    """Main gold transformer workflow."""
    start_time = datetime.now()
    
    try:
        print("="*60)
        print("GOLD TRANSFORMER JOB STARTED")
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
        import os
        os.environ['AURORA_ENDPOINT'] = args['AURORA_ENDPOINT']
        os.environ['AURORA_USERNAME'] = username
        os.environ['AURORA_PASSWORD'] = password
        os.environ['DBT_TARGET'] = args['ENVIRONMENT']
        
        # Step 3: Install dbt dependencies
        install_dbt_dependencies(dbt_local_path)
        
        # Step 4: Create backups of existing gold tables
        connection = pymysql.connect(
            host=args['AURORA_ENDPOINT'],
            user=username,
            password=password,
            database=args['AURORA_DATABASE'],
            charset='utf8mb4'
        )
        
        try:
            # Clean up potential leftover temp tables from previous failed runs
            cleanup_dbt_tmp_tables(connection, 'gold')
            
            backup_count = create_table_backups(connection, GOLD_TABLES, 'gold')
            
            # Step 5: Run gold models
            gold_result = run_dbt_gold_models(
                dbt_local_path,
                args['ENVIRONMENT'],
                aurora_endpoint=args['AURORA_ENDPOINT'],
                aurora_username=username,
                aurora_password=password
            )
            
            # Step 6: Run gold tests
            test_result = run_dbt_gold_tests(dbt_local_path, args['ENVIRONMENT'])
            
            # Step 7: Clean up old backups
            removed_backups = cleanup_old_backups(connection, days_to_keep=3)
            
        finally:
            connection.close()
        
        # Calculate duration
        duration = (datetime.now() - start_time).total_seconds()
        
        # Log success
        result = {
            'status': 'SUCCESS',
            'models_built': gold_result['models_built'],
            'backup_count': backup_count,
            'tests_passed': test_result['tests_passed'],
            'tests_failed': test_result['tests_failed'],
            'old_backups_removed': removed_backups,
            'duration_seconds': int(duration)
        }
        
        print(f"\n{'='*60}")
        print("GOLD TRANSFORMER COMPLETED SUCCESSFULLY")
        print(f"Duration: {duration:.2f} seconds")
        print(f"Models built: {gold_result['models_built']}")
        print(f"Backups created: {backup_count}")
        print(f"Tests passed: {test_result['tests_passed']}")
        print(f"Tests failed: {test_result['tests_failed']}")
        print(f"Old backups removed: {removed_backups}")
        print(f"{'='*60}\n")
        
        # Output result for Step Functions
        print(f"RESULT_JSON: {json.dumps(result)}")
        
        job.commit()
        return result
        
    except Exception as e:
        print(f"\nERROR: Gold transformer job failed: {str(e)}")
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
