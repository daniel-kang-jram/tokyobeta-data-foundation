"""
Lambda Function: Table Freshness Checker
Checks staging table freshness and publishes metrics to CloudWatch.
Sends SNS alert if any table is > 2 days old.
"""

import json
import os
from datetime import datetime, timedelta
import boto3
import pymysql

# Environment variables
AURORA_ENDPOINT = os.environ['AURORA_ENDPOINT']
AURORA_SECRET_ARN = os.environ['AURORA_SECRET_ARN']
SNS_TOPIC_ARN = os.environ['SNS_TOPIC_ARN']

# AWS clients
secretsmanager = boto3.client('secretsmanager')
cloudwatch = boto3.client('cloudwatch')
sns = boto3.client('sns')

TABLES_TO_CHECK = ${jsonencode(tables)}
WARN_DAYS = 1
ERROR_DAYS = 2


def get_db_credentials():
    """Retrieve database credentials from Secrets Manager."""
    secret = secretsmanager.get_secret_value(SecretId=AURORA_SECRET_ARN)
    return json.loads(secret['SecretString'])


def check_table_freshness(cursor, table_name):
    """Check how old a table's data is."""
    cursor.execute(f"""
        SELECT 
            COUNT(*) as row_count,
            MAX(updated_at) as last_updated,
            DATEDIFF(CURRENT_DATE, DATE(MAX(updated_at))) as days_old
        FROM staging.{table_name}
    """)
    
    result = cursor.fetchone()
    return {
        'table': table_name,
        'row_count': result[0],
        'last_updated': result[1].isoformat() if result[1] else None,
        'days_old': result[2] if result[2] is not None else 999
    }


def publish_metric(table_name, days_old):
    """Publish freshness metric to CloudWatch."""
    cloudwatch.put_metric_data(
        Namespace='TokyoBeta/DataQuality',
        MetricData=[
            {
                'MetricName': f'Staging{table_name.capitalize()}DaysOld',
                'Value': days_old,
                'Unit': 'None',
                'Timestamp': datetime.utcnow()
            }
        ]
    )


def send_alert(stale_tables):
    """Send SNS alert for stale tables."""
    message = "⚠️ STAGING TABLE FRESHNESS ALERT\\n\\n"
    message += "The following staging tables are stale:\\n\\n"
    
    for table_info in stale_tables:
        status = "🔴 CRITICAL" if table_info['days_old'] >= ERROR_DAYS else "⚠️ WARNING"
        message += f"{status} staging.{table_info['table']}\\n"
        message += f"  Last updated: {table_info['last_updated']}\\n"
        message += f"  Days old: {table_info['days_old']}\\n"
        message += f"  Row count: {table_info['row_count']:,}\\n\\n"
    
    message += "Action required:\\n"
    message += "1. Check if EC2 cron job is generating dumps\\n"
    message += "2. Verify Glue staging_loader job is running\\n"
    message += "3. Check S3 for recent dump files\\n\\n"
    message += "Manual fix command:\\n"
    message += "python3 scripts/emergency_staging_fix.py --tables movings tenants rooms\\n"
    
    sns.publish(
        TopicArn=SNS_TOPIC_ARN,
        Subject=f"⚠️ Staging Table Freshness Alert - {len(stale_tables)} tables stale",
        Message=message
    )


def lambda_handler(event, context):
    """Main Lambda handler."""
    print(f"Checking table freshness for: {TABLES_TO_CHECK}")
    
    # Get database credentials
    creds = get_db_credentials()
    
    # Connect to database
    connection = pymysql.connect(
        host=AURORA_ENDPOINT.split(':')[0],
        user=creds['username'],
        password=creds['password'],
        database=creds.get('dbname', 'tokyobeta'),
        charset='utf8mb4'
    )
    
    try:
        cursor = connection.cursor()
        
        stale_tables = []
        results = []
        
        for table in TABLES_TO_CHECK:
            try:
                table_info = check_table_freshness(cursor, table)
                results.append(table_info)
                
                # Publish metric to CloudWatch
                publish_metric(table, table_info['days_old'])
                
                # Check if stale
                if table_info['days_old'] >= WARN_DAYS:
                    stale_tables.append(table_info)
                    print(f"⚠️ Table {table} is {table_info['days_old']} days old")
                else:
                    print(f"✅ Table {table} is fresh ({table_info['days_old']} days old)")
                    
            except Exception as e:
                print(f"Error checking {table}: {e}")
                # Publish error metric
                publish_metric(table, 999)
        
        # Send alert if any tables are stale
        if stale_tables:
            send_alert(stale_tables)
            print(f"Alert sent for {len(stale_tables)} stale tables")
        
        return {
            'statusCode': 200 if not stale_tables else 400,
            'body': json.dumps({
                'message': 'Freshness check complete',
                'stale_count': len(stale_tables),
                'results': results
            })
        }
        
    finally:
        connection.close()
