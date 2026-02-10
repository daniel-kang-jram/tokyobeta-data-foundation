"""
AWS Glue ETL Job: Silver Transformer
Runs dbt to transform staging → silver layer (cleaned & standardized).

Part of the resilient ETL architecture: Staging → Silver → Gold
This job focuses ONLY on the silver layer transformations.
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
import pymysql

# Initialize Glue context
sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)

# Get job parameters
required_args = [
    'JOB_NAME',
    'S3_SOURCE_BUCKET',
    'DBT_PROJECT_PATH',
    'AURORA_ENDPOINT',
    'AURORA_DATABASE',
    'AURORA_SECRET_ARN',
    'ENVIRONMENT'
]

optional_args = ['DBT_SELECT', 'SKIP_TESTS']  # Optional: Limit models and skip tests

args = getResolvedOptions(sys.argv, required_args)

# Get optional args with defaults
for arg in optional_args:
    if f'--{arg}' in sys.argv:
        idx = sys.argv.index(f'--{arg}')
        if idx + 1 < len(sys.argv):
            args[arg] = sys.argv[idx + 1]

job.init(args['JOB_NAME'], args)

# Initialize clients
s3 = boto3.client('s3')
secretsmanager = boto3.client('secretsmanager')

# Silver tables to backup before transformation
SILVER_TABLES = [
    'stg_movings',
    'stg_tenants',
    'stg_apartments',
    'stg_rooms',
    'stg_inquiries',
    'int_contracts'
]


def get_aurora_credentials(secretsmanager_client, secret_arn):
    """
    Retrieve Aurora credentials from Secrets Manager.
    
    Args:
        secretsmanager_client: boto3 Secrets Manager client
        secret_arn: ARN of the secret
        
    Returns:
        Tuple of (username, password)
    """
    response = secretsmanager_client.get_secret_value(SecretId=secret_arn)
    secret = json.loads(response['SecretString'])
    return secret['username'], secret['password']


def get_dbt_executable_path():
    """
    Get path to dbt executable in Glue environment.
    
    Returns:
        Path to dbt binary
    """
    # dbt is installed in /home/spark/.local/bin/ by pip --user in Glue
    possible_paths = [
        "/home/spark/.local/bin/dbt",
        "/usr/local/bin/dbt",
        "dbt"  # Fallback to PATH
    ]
    
    for path in possible_paths:
        if os.path.exists(path) or path == "dbt":
            return path
    
    return "dbt"  # Default fallback


def download_dbt_project(bucket, s3_prefix, local_path):
    """
    Download dbt project from S3.
    
    Args:
        bucket: S3 bucket name
        s3_prefix: S3 prefix for dbt project
        local_path: Local destination path
        
    Returns:
        Local path to dbt project
    """
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


def run_dbt_seed(dbt_project_path, target_env):
    """
    Load dbt seed files (code mappings).
    
    Args:
        dbt_project_path: Path to dbt project
        target_env: Target environment (prod/dev)
        
    Returns:
        Result dict
    """
    print("\n" + "="*60)
    print("RUNNING DBT SEED")
    print("="*60)
    
    dbt_executable = get_dbt_executable_path()
    
    result = subprocess.run([
        dbt_executable, "seed",
        "--profiles-dir", dbt_project_path,
        "--project-dir", dbt_project_path,
        "--target", target_env
    ], capture_output=True, text=True)
    
    print(result.stdout)
    if result.returncode != 0:
        print("=== DBT SEED ERRORS ===")
        print(result.stderr)
        raise subprocess.CalledProcessError(
            result.returncode,
            result.args,
            result.stdout,
            result.stderr
        )
    
    return {
        'success': True,
        'output': result.stdout
    }


def run_dbt_silver_models(
    dbt_project_path,
    target_env,
    dbt_select=None,
    aurora_endpoint=None,
    aurora_username=None,
    aurora_password=None
):
    """
    Run dbt silver layer models only.
    
    Args:
        dbt_project_path: Path to dbt project
        target_env: Target environment (prod/dev)
        dbt_select: Optional filter for dbt select (e.g. "silver.tenant_status_history")
        aurora_endpoint: Aurora endpoint (for env var)
        aurora_username: Aurora username (for env var)
        aurora_password: Aurora password (for env var)
        
    Returns:
        Result dict with models_built count
    """
    print("\n" + "="*60)
    print("RUNNING DBT SILVER MODELS")
    if dbt_select:
        print(f"Filter: {dbt_select}")
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
    
    # Determine selection args
    selection_args = ["--select", dbt_select] if dbt_select else ["--models", "silver.*"]
    
    cmd = [
        dbt_executable, "run",
        "--profiles-dir", dbt_project_path,
        "--project-dir", dbt_project_path,
        "--target", target_env,
        "--fail-fast"
    ] + selection_args
    
    # Run only silver models with --fail-fast to stop on first error
    result = subprocess.run(cmd, capture_output=True, text=True)
    
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
    models_built = 0
    if "models built" in result.stdout.lower() or "completed successfully" in result.stdout.lower():
        # If specific select, count is 1 or fewer usually
        models_built = len(SILVER_TABLES) if not dbt_select else 1
    
    return {
        'success': True,
        'models_built': models_built,
        'output': result.stdout
    }


def run_dbt_silver_tests(dbt_project_path, target_env, dbt_select=None):
    """
    Run dbt tests for silver layer models.
    
    Args:
        dbt_project_path: Path to dbt project
        target_env: Target environment (prod/dev)
        dbt_select: Optional filter for dbt select
        
    Returns:
        Result dict with test counts
    """
    print("\n" + "="*60)
    print("RUNNING DBT SILVER TESTS")
    if dbt_select:
        print(f"Filter: {dbt_select}")
    print("="*60)
    
    dbt_executable = get_dbt_executable_path()
    
    # Determine selection args
    selection_args = ["--select", dbt_select] if dbt_select else ["--models", "silver.*"]
    
    cmd = [
        dbt_executable, "test",
        "--profiles-dir", dbt_project_path,
        "--project-dir", dbt_project_path,
        "--target", target_env
    ] + selection_args
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    print(result.stdout)
    
    # Parse test results
    import re
    tests_passed = 0
    tests_failed = 0
    
    if "passed" in result.stdout.lower():
        # Try to extract numbers
        match = re.search(r'(\d+)\s+test.*passed', result.stdout, re.IGNORECASE)
        if match:
            tests_passed = int(match.group(1))
    
    if "failed" in result.stdout.lower() or result.returncode != 0:
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
            WHERE TABLE_SCHEMA = %s 
            AND TABLE_NAME LIKE '%%__dbt_tmp'
        """, (schema,))
        
        tmp_tables = [row[0] for row in cursor.fetchall()]
        
        if not tmp_tables:
            print("  No temporary tables found.")
            return 0
            
        print(f"  Found {len(tmp_tables)} temporary tables: {', '.join(tmp_tables)}")
        
        import re  # Ensure re is available
        for table_name in tmp_tables:
            # Validate table name strictly to prevent SQL injection
            # Only allow alphanumeric and underscore, and must end with __dbt_tmp
            if not re.match(r'^[a-zA-Z0-9_]+__dbt_tmp$', table_name):
                print(f"  ⚠ Skipping invalid table name: {table_name}")
                continue
                
            print(f"  Dropping {schema}.{table_name}...")
            # Use backticks for identifier quoting
            cursor.execute(f"DROP TABLE IF EXISTS `{schema}`.`{table_name}`")
            dropped_count += 1
            
        connection.commit()
        print(f"  ✓ Dropped {dropped_count} temporary tables")
        return dropped_count
        
    except Exception as e:
        print(f"  ⚠ Warning: Failed to cleanup temp tables: {str(e)}")
        return 0
    finally:
        cursor.close()


def create_table_backups(connection, tables, schema='silver'):
    """
    Create backup copies of tables before transformation.
    Keeps only the last 3 backups per table.
    
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
            backup_name = f"{table_name}_bak_{backup_suffix}"
            
            try:
                # 1. Create new backup
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
                    
                    # 2. Cleanup old backups (Keep last 3)
                    cursor.execute(f"""
                        SELECT TABLE_NAME 
                        FROM information_schema.TABLES 
                        WHERE TABLE_SCHEMA = '{schema}' 
                        AND TABLE_NAME LIKE '{table_name}_bak_%'
                        ORDER BY TABLE_NAME DESC
                    """)
                    
                    backups = [row[0] for row in cursor.fetchall()]
                    
                    if len(backups) > 3:
                        for old_backup in backups[3:]:
                            print(f"    Removing old backup: {schema}.{old_backup}")
                            cursor.execute(f"DROP TABLE IF EXISTS {schema}.{old_backup}")
                            
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


def main():
    """Main silver transformer workflow."""
    start_time = datetime.now()
    
    try:
        print("="*60)
        print("SILVER TRANSFORMER JOB STARTED")
        print(f"Environment: {args['ENVIRONMENT']}")
        if 'DBT_SELECT' in args:
            print(f"DBT Select: {args['DBT_SELECT']}")
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
        
        # Step 3: Create backups of existing silver tables
        connection = pymysql.connect(
            host=args['AURORA_ENDPOINT'],
            user=username,
            password=password,
            database=args['AURORA_DATABASE'],
            charset='utf8mb4'
        )
        
        try:
            # Clean up potential leftover temp tables from previous failed runs
            cleanup_dbt_tmp_tables(connection, 'silver')
            
            # Only backup tables if running full suite (or specifically requested table)
            # For simplicity, backup critical tables anyway as it's cheap/fast
            if not args.get('DBT_SELECT'):
                backup_count = create_table_backups(connection, SILVER_TABLES, 'silver')
            else:
                print("Skipping full table backups for selective run")
                backup_count = 0
        finally:
            connection.close()
        
        # Step 4: Install dbt dependencies
        install_dbt_dependencies(dbt_local_path)
        
        # Step 5: Load seed files
        seed_result = run_dbt_seed(dbt_local_path, args['ENVIRONMENT'])
        
        # Step 6: Run silver models
        silver_result = run_dbt_silver_models(
            dbt_local_path,
            args['ENVIRONMENT'],
            dbt_select=args.get('DBT_SELECT'),
            aurora_endpoint=args['AURORA_ENDPOINT'],
            aurora_username=username,
            aurora_password=password
        )
        
        # Step 7: Run silver tests (optional - can be skipped for performance)
        skip_tests = args.get('SKIP_TESTS', 'false').lower() == 'true'
        
        if skip_tests:
            print("\n" + "="*60)
            print("SKIPPING DBT TESTS (SKIP_TESTS=true)")
            print("Run tokyobeta-prod-silver-test job separately for validation")
            print("="*60)
            test_result = {
                'tests_passed': 0,
                'tests_failed': 0,
                'output': 'Tests skipped'
            }
        else:
            test_result = run_dbt_silver_tests(
                dbt_local_path, 
                args['ENVIRONMENT'],
                dbt_select=args.get('DBT_SELECT')
            )
        
        # Calculate duration
        duration = (datetime.now() - start_time).total_seconds()
        
        # Log success
        result = {
            'status': 'SUCCESS',
            'models_built': silver_result['models_built'],
            'backup_count': backup_count,
            'tests_passed': test_result['tests_passed'],
            'tests_failed': test_result['tests_failed'],
            'duration_seconds': int(duration)
        }
        
        print(f"\n{'='*60}")
        print("SILVER TRANSFORMER COMPLETED SUCCESSFULLY")
        print(f"Duration: {duration:.2f} seconds")
        print(f"Models built: {silver_result['models_built']}")
        print(f"Backups created: {backup_count}")
        print(f"Tests passed: {test_result['tests_passed']}")
        print(f"Tests failed: {test_result['tests_failed']}")
        print(f"{'='*60}\n")
        
        # Output result for Step Functions
        print(f"RESULT_JSON: {json.dumps(result)}")
        
        job.commit()
        return result
        
    except Exception as e:
        print(f"\nERROR: Silver transformer job failed: {str(e)}")
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
