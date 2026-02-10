#!/usr/bin/env python3
"""
Comprehensive System Validation Script
Checks all key components of the data pipeline
"""

import subprocess
import sys
import pymysql
import os

AWS_PROFILE = "gghouse"
AWS_REGION = "ap-northeast-1"

DB_CONFIG = {
    "host": "tokyobeta-prod-aurora-cluster-public.cluster-cr46qo6y4bbb.ap-northeast-1.rds.amazonaws.com",
    "port": 3306,
    "user": "admin",
    "password": "K6ghcWTq4p-zlidRJ2<AJX<w$zN<a8dU",
    "database": "tokyobeta",
}

def run_aws_command(command):
    """Run AWS CLI command with gghouse profile."""
    os.environ['AWS_PROFILE'] = AWS_PROFILE
    os.environ['AWS_REGION'] = AWS_REGION
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr

def check_pass(msg):
    print(f"✅ PASS: {msg}")

def check_fail(msg):
    print(f"❌ FAIL: {msg}")

def check_warn(msg):
    print(f"⚠️  WARN: {msg}")

def main():
    print("Tokyo Beta Data Pipeline - System Validation")
    print("=" * 60)
    print("")

    # 1. Check AWS Profile
    print("1️⃣  Checking AWS Profile...")
    rc, out, err = run_aws_command("aws sts get-caller-identity --query Account --output text")
    if rc == 0:
        account = out.strip()
        if account == "343881458651":
            check_pass(f"AWS Account: {account} (gghouse)")
        else:
            check_fail(f"Wrong AWS Account: {account} (expected 343881458651)")
            sys.exit(1)
    else:
        check_fail(f"AWS CLI error: {err}")
        sys.exit(1)

    # 2. Check S3 Dumps
    print("")
    print("2️⃣  Checking S3 Dump Files...")
    rc, out, err = run_aws_command("aws s3 ls s3://jram-gghouse/dumps/ | tail -1")
    if rc == 0 and out:
        latest = out.strip().split()[-1]
        check_pass(f"Latest dump: {latest}")
    else:
        check_fail("No dumps found in S3")

    # 3. Check Glue Jobs
    print("")
    print("3️⃣  Checking Glue Jobs...")
    jobs = ["staging-loader", "silver-transformer", "gold-transformer"]
    for job in jobs:
        job_name = f"tokyobeta-prod-{job}"
        rc, out, err = run_aws_command(f"aws glue get-job --job-name {job_name} --query 'Job.Name' --output text")
        if rc == 0 and job_name in out:
            check_pass(f"{job_name} exists")
            
            # Check last run
            rc2, out2, err2 = run_aws_command(
                f"aws glue get-job-runs --job-name {job_name} --max-items 1 "
                f"--query 'JobRuns[0].JobRunState' --output text"
            )
            if rc2 == 0 and out2.strip():
                state = out2.strip()
                if state == "SUCCEEDED":
                    check_pass(f"  Last run: {state}")
                elif state == "RUNNING":
                    check_warn(f"  Currently: {state}")
                else:
                    check_fail(f"  Last run: {state}")
        else:
            check_fail(f"{job_name} not found")

    # 4. Check Table Freshness
    print("")
    print("4️⃣  Checking Database Table Freshness...")
    rc, out, err = run_aws_command("python3 scripts/emergency_staging_fix.py --check-only 2>/dev/null")
    if rc == 0:
        lines = out.strip().split('\n')
        for line in lines[-6:]:
            if 'staging.' in line:
                print(f"  {line}")
    
    # 5. Check Key Tables
    print("")
    print("5️⃣  Checking Key Tables Exist...")
    try:
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        tables = [
            ("silver.tokyo_beta_tenant_room_info", "tokyo_beta_tenant_room_info"),
            ("silver.int_contracts", "int_contracts"),
            ("gold.daily_activity_summary", "daily_activity_summary"),
        ]
        
        for schema_table, table in tables:
            schema, tbl = schema_table.split('.')
            cursor.execute(f"SELECT COUNT(*) FROM {schema}.{tbl}")
            count = cursor.fetchone()[0]
            if count > 0:
                check_pass(f"{schema_table}: {count:,} rows")
            else:
                check_fail(f"{schema_table}: Empty")
        
        conn.close()
    except Exception as e:
        check_fail(f"Database error: {e}")

    # 6. Check CloudWatch Alarms
    print("")
    print("6️⃣  Checking Monitoring...")
    rc, out, err = run_aws_command(
        "aws cloudwatch describe-alarms --alarm-name-prefix tokyobeta-prod "
        "--query 'length(MetricAlarms)' --output text"
    )
    if rc == 0:
        count = out.strip()
        if count and int(count) > 0:
            check_pass(f"CloudWatch alarms: {count} configured")
        else:
            check_warn("No CloudWatch alarms found")
    
    print("")
    print("=" * 60)
    print("VALIDATION COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    main()
