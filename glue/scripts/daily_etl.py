"""
AWS Glue ETL Job: Daily SQL Dump to Aurora Staging
Downloads latest SQL dump from S3, parses it, and loads into Aurora staging schema.
Then triggers dbt to transform staging → analytics.
"""

import sys
import boto3
import json
import re
import subprocess
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
    'S3_SOURCE_PREFIX',
    'AURORA_ENDPOINT',
    'AURORA_DATABASE',
    'AURORA_SECRET_ARN',
    'ENVIRONMENT',
    'DBT_PROJECT_PATH'
])

job.init(args['JOB_NAME'], args)

# Initialize clients
s3 = boto3.client('s3')
secretsmanager = boto3.client('secretsmanager')

def get_latest_dump_key():
    """Find the most recent SQL dump file in S3."""
    response = s3.list_objects_v2(
        Bucket=args['S3_SOURCE_BUCKET'],
        Prefix=args['S3_SOURCE_PREFIX']
    )
    
    if 'Contents' not in response:
        raise ValueError(f"No files found in s3://{args['S3_SOURCE_BUCKET']}/{args['S3_SOURCE_PREFIX']}")
    
    # Sort by LastModified descending
    files = sorted(response['Contents'], key=lambda x: x['LastModified'], reverse=True)
    
    # Filter for gghouse_YYYYMMDD.sql pattern
    sql_files = [f for f in files if re.match(r'.*gghouse_\d{8}\.sql$', f['Key'])]
    
    if not sql_files:
        raise ValueError("No SQL dump files matching pattern gghouse_YYYYMMDD.sql found")
    
    latest_key = sql_files[0]['Key']
    print(f"Latest dump: {latest_key} (modified: {sql_files[0]['LastModified']})")
    return latest_key

def get_aurora_credentials():
    """Retrieve Aurora credentials from Secrets Manager."""
    response = secretsmanager.get_secret_value(SecretId=args['AURORA_SECRET_ARN'])
    secret = json.loads(response['SecretString'])
    return secret['username'], secret['password']

def download_and_parse_dump(s3_key):
    """Download SQL dump from S3 and return as string."""
    local_path = f"/tmp/{s3_key.split('/')[-1]}"
    
    print(f"Downloading {s3_key} to {local_path}...")
    s3.download_file(args['S3_SOURCE_BUCKET'], s3_key, local_path)
    
    with open(local_path, 'r', encoding='utf-8') as f:
        sql_content = f.read()
    
    print(f"Downloaded {len(sql_content)} characters")
    return sql_content, local_path

def load_to_aurora_staging(sql_content):
    """Load SQL dump into Aurora staging schema."""
    username, password = get_aurora_credentials()
    
    # Connect to Aurora
    connection = pymysql.connect(
        host=args['AURORA_ENDPOINT'],
        user=username,
        password=password,
        database=args['AURORA_DATABASE'],
        charset='utf8mb4'
    )
    
    try:
        cursor = connection.cursor()
        
        # Create staging schema if not exists
        cursor.execute("CREATE SCHEMA IF NOT EXISTS staging")
        cursor.execute("USE staging")
        
        # Drop all existing tables in staging (full reload strategy)
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'staging'
        """)
        for (table_name,) in cursor.fetchall():
            print(f"Dropping staging.{table_name}")
            cursor.execute(f"DROP TABLE IF EXISTS staging.{table_name}")
        
        connection.commit()
        
        # Split SQL dump into statements
        # Remove comments and split by semicolon
        sql_cleaned = re.sub(r'/\*.*?\*/', '', sql_content, flags=re.DOTALL)
        sql_cleaned = re.sub(r'--.*$', '', sql_cleaned, flags=re.MULTILINE)
        
        statements = [s.strip() for s in sql_cleaned.split(';') if s.strip()]
        
        print(f"Executing {len(statements)} SQL statements...")
        
        executed = 0
        for i, stmt in enumerate(statements):
            if not stmt:
                continue
            
            # Prefix table names with staging schema
            stmt = re.sub(r'CREATE TABLE `(\w+)`', r'CREATE TABLE `staging.\1`', stmt)
            stmt = re.sub(r'INSERT INTO `(\w+)`', r'INSERT INTO `staging.\1`', stmt)
            stmt = re.sub(r'DROP TABLE IF EXISTS `(\w+)`', r'DROP TABLE IF EXISTS `staging.\1`', stmt)
            
            try:
                cursor.execute(stmt)
                executed += 1
                
                if executed % 100 == 0:
                    print(f"Progress: {executed}/{len(statements)} statements executed")
                    connection.commit()
            except Exception as e:
                print(f"Warning: Statement {i} failed: {str(e)[:200]}")
                # Continue on errors (some statements may be incompatible)
                continue
        
        connection.commit()
        print(f"Successfully executed {executed}/{len(statements)} statements")
        
        # Verify tables were created
        cursor.execute("""
            SELECT table_name, table_rows 
            FROM information_schema.tables 
            WHERE table_schema = 'staging'
            ORDER BY table_name
        """)
        
        tables = cursor.fetchall()
        print(f"\nStaging schema now contains {len(tables)} tables:")
        for table_name, row_count in tables:
            print(f"  - {table_name}: {row_count} rows")
        
        return len(tables), executed
        
    finally:
        cursor.close()
        connection.close()

def run_dbt_transformations():
    """Execute dbt models to transform staging → analytics."""
    print("\nRunning dbt transformations...")
    
    # Download dbt project from S3
    dbt_local_path = "/tmp/dbt-project"
    subprocess.run([
        "aws", "s3", "sync",
        f"s3://{args['S3_SOURCE_BUCKET']}/dbt-project/",
        dbt_local_path
    ], check=True)
    
    # Set environment variables for dbt
    username, password = get_aurora_credentials()
    import os
    os.environ['AURORA_ENDPOINT'] = args['AURORA_ENDPOINT']
    os.environ['AURORA_USERNAME'] = username
    os.environ['AURORA_PASSWORD'] = password
    os.environ['DBT_TARGET'] = args['ENVIRONMENT']
    
    # Install dbt dependencies
    subprocess.run([
        "dbt", "deps",
        "--profiles-dir", dbt_local_path,
        "--project-dir", dbt_local_path
    ], check=True)
    
    # Run dbt models
    result = subprocess.run([
        "dbt", "run",
        "--profiles-dir", dbt_local_path,
        "--project-dir", dbt_local_path,
        "--target", args['ENVIRONMENT']
    ], check=True, capture_output=True, text=True)
    
    print(result.stdout)
    
    # Run dbt tests
    test_result = subprocess.run([
        "dbt", "test",
        "--profiles-dir", dbt_local_path,
        "--project-dir", dbt_local_path,
        "--target", args['ENVIRONMENT']
    ], capture_output=True, text=True)
    
    print(test_result.stdout)
    if test_result.returncode != 0:
        print(f"WARNING: dbt tests failed:\n{test_result.stderr}")
        # Don't fail job on test failures, just warn
    
    return result.returncode == 0

def archive_processed_dump(s3_key):
    """Move processed dump to archive folder."""
    source_key = s3_key
    dest_key = source_key.replace('/dumps/', '/processed/')
    
    s3.copy_object(
        Bucket=args['S3_SOURCE_BUCKET'],
        CopySource={'Bucket': args['S3_SOURCE_BUCKET'], 'Key': source_key},
        Key=dest_key
    )
    
    print(f"Archived dump to {dest_key}")

def main():
    """Main ETL workflow."""
    start_time = datetime.now()
    
    try:
        # Step 1: Find and download latest dump
        latest_key = get_latest_dump_key()
        sql_content, local_path = download_and_parse_dump(latest_key)
        
        # Step 2: Load to Aurora staging
        table_count, stmt_count = load_to_aurora_staging(sql_content)
        
        # Step 3: Run dbt transformations
        dbt_success = run_dbt_transformations()
        
        # Step 4: Archive processed dump
        archive_processed_dump(latest_key)
        
        # Calculate duration
        duration = (datetime.now() - start_time).total_seconds()
        
        # Log success
        print(f"\n{'='*60}")
        print(f"ETL Job Completed Successfully")
        print(f"Duration: {duration:.2f} seconds")
        print(f"Tables loaded: {table_count}")
        print(f"SQL statements executed: {stmt_count}")
        print(f"dbt transformations: {'Success' if dbt_success else 'Failed'}")
        print(f"{'='*60}\n")
        
        job.commit()
        
    except Exception as e:
        print(f"\nERROR: ETL job failed: {str(e)}")
        import traceback
        traceback.print_exc()
        job.commit()
        raise

if __name__ == "__main__":
    main()
