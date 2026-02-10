"""
AWS Glue Job: Occupancy KPI Updater (Incremental)

Computes daily occupancy metrics from silver.tenant_room_snapshot_daily.
Runs incrementally: only target date + small lookback window (3 days).

Daily runtime: Constant (processes ~4 dates regardless of history size).
"""

import sys
import boto3
import json
import pymysql
from datetime import datetime, date, timedelta
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
    'AURORA_ENDPOINT',
    'AURORA_DATABASE',
    'AURORA_SECRET_ARN',
    'TARGET_DATE',  # Optional: specific date to process (default: today)
    'LOOKBACK_DAYS'  # Optional: lookback window (default: 3)
])

job.init(args['JOB_NAME'], args)

# Initialize clients
secretsmanager = boto3.client('secretsmanager')

# Constants
TOTAL_PHYSICAL_ROOMS = 16108
OCCUPIED_STATUS_CODES = [4, 5, 6, 7, 9, 10, 11, 12, 13, 14, 15]


def get_aurora_credentials():
    """Retrieve Aurora credentials from Secrets Manager."""
    response = secretsmanager.get_secret_value(SecretId=args['AURORA_SECRET_ARN'])
    secret = json.loads(response['SecretString'])
    return secret['username'], secret['password']


def get_connection():
    """Get Aurora MySQL connection."""
    username, password = get_aurora_credentials()
    
    connection = pymysql.connect(
        host=args['AURORA_ENDPOINT'],
        user=username,
        password=password,
        database=args['AURORA_DATABASE'],
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )
    return connection


def ensure_kpi_table_exists(cursor):
    """Create gold.occupancy_daily_metrics table if not exists."""
    print("Ensuring gold.occupancy_daily_metrics table exists...")
    
    create_sql = """
        CREATE TABLE IF NOT EXISTS gold.occupancy_daily_metrics (
            snapshot_date DATE NOT NULL,
            applications INT COMMENT '申込: First appearance of pairs in status 4 or 5',
            new_moveins INT COMMENT '新規入居者: Pairs with move_in_date = snapshot_date',
            new_moveouts INT COMMENT '新規退去者: Pairs with moveout date = snapshot_date',
            occupancy_delta INT COMMENT '稼働室数増減: new_moveins - new_moveouts',
            period_start_rooms INT COMMENT '期首稼働室数: Occupied count on previous day',
            period_end_rooms INT COMMENT '期末稼働室数: period_start + delta',
            occupancy_rate DECIMAL(5,4) COMMENT '稼働率: period_end / 16108',
            
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            
            PRIMARY KEY (snapshot_date),
            INDEX idx_snapshot_date (snapshot_date),
            INDEX idx_occupancy_rate (occupancy_rate)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        COMMENT='Daily occupancy KPI metrics (incremental upsert)'
    """
    
    cursor.execute(create_sql)
    print("✓ gold.occupancy_daily_metrics table verified/created")


def compute_kpi_for_dates(cursor, target_dates):
    """
    Compute occupancy KPIs for specific dates.
    
    Args:
        cursor: pymysql cursor
        target_dates: List of dates to process
        
    Returns:
        Number of rows computed
    """
    if not target_dates:
        return 0
        
    print(f"Computing KPIs for {len(target_dates)} dates...")
    
    for target_date in target_dates:
        print(f"  Processing {target_date}...")
        
        # Determine if this is a past/present vs future date
        is_past_or_today = target_date <= date.today()
        
        # --- Metric 1: 申込 (Applications) ---
        # Count first appearance of (tenant_id, apartment_id, room_id) where status IN (4, 5)
        cursor.execute("""
            SELECT COUNT(DISTINCT CONCAT(tenant_id, '-', apartment_id, '-', room_id)) as count
            FROM (
                SELECT 
                    tenant_id,
                    apartment_id,
                    room_id,
                    MIN(snapshot_date) as first_appearance
                FROM silver.tenant_room_snapshot_daily
                WHERE management_status_code IN (4, 5)
                GROUP BY tenant_id, apartment_id, room_id
            ) first_apps
            WHERE first_appearance = %s
        """, (target_date,))
        applications = cursor.fetchone()['count']
        
        # --- Metric 2: 新規入居者 (New Move-ins) ---
        # Past/today: status IN (4,5,6,7,9) AND move_in_date = target
        # Future: status IN (4,5) AND move_in_date = target
        if is_past_or_today:
            movein_status_filter = "(4,5,6,7,9)"
        else:
            movein_status_filter = "(4,5)"
            
        cursor.execute(f"""
            SELECT COUNT(DISTINCT CONCAT(tenant_id, '-', apartment_id, '-', room_id)) as count
            FROM silver.tenant_room_snapshot_daily
            WHERE snapshot_date = %s
            AND move_in_date = %s
            AND management_status_code IN {movein_status_filter}
        """, (target_date, target_date))
        new_moveins = cursor.fetchone()['count']
        
        # --- Metric 3: 新規退去者 (New Move-outs) ---
        # Past/today: moveout_plans_date = target
        # Future: moveout_date = target
        if is_past_or_today:
            cursor.execute("""
                SELECT COUNT(DISTINCT CONCAT(tenant_id, '-', apartment_id, '-', room_id)) as count
                FROM silver.tenant_room_snapshot_daily
                WHERE snapshot_date = %s
                AND moveout_plans_date = %s
            """, (target_date, target_date))
        else:
            cursor.execute("""
                SELECT COUNT(DISTINCT CONCAT(tenant_id, '-', apartment_id, '-', room_id)) as count
                FROM silver.tenant_room_snapshot_daily
                WHERE snapshot_date = %s
                AND moveout_date = %s
            """, (target_date, target_date))
        new_moveouts = cursor.fetchone()['count']
        
        # --- Metric 4: 稼働室数増減 (Occupancy Delta) ---
        occupancy_delta = new_moveins - new_moveouts
        
        # --- Metric 5: 期首稼働室数 (Period Start Rooms) ---
        # Count occupied pairs on previous day
        previous_date = target_date - timedelta(days=1)
        cursor.execute("""
            SELECT COUNT(DISTINCT CONCAT(tenant_id, '-', apartment_id, '-', room_id)) as count
            FROM silver.tenant_room_snapshot_daily
            WHERE snapshot_date = %s
            AND management_status_code IN (4,5,6,7,9,10,11,12,13,14,15)
        """, (previous_date,))
        result = cursor.fetchone()
        period_start_rooms = result['count'] if result else 0
        
        # --- Metric 6: 期末稼働室数 (Period End Rooms) ---
        period_end_rooms = period_start_rooms + occupancy_delta
        
        # --- Metric 7: 稼働率 (Occupancy Rate) ---
        occupancy_rate = period_end_rooms / TOTAL_PHYSICAL_ROOMS
        
        # Insert or update
        cursor.execute("""
            INSERT INTO gold.occupancy_daily_metrics
            (snapshot_date, applications, new_moveins, new_moveouts, 
             occupancy_delta, period_start_rooms, period_end_rooms, occupancy_rate)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                applications = VALUES(applications),
                new_moveins = VALUES(new_moveins),
                new_moveouts = VALUES(new_moveouts),
                occupancy_delta = VALUES(occupancy_delta),
                period_start_rooms = VALUES(period_start_rooms),
                period_end_rooms = VALUES(period_end_rooms),
                occupancy_rate = VALUES(occupancy_rate),
                updated_at = CURRENT_TIMESTAMP
        """, (target_date, applications, new_moveins, new_moveouts, 
              occupancy_delta, period_start_rooms, period_end_rooms, occupancy_rate))
        
        print(f"    ✓ {target_date}: apps={applications}, moveins={new_moveins}, moveouts={new_moveouts}, "
              f"delta={occupancy_delta:+d}, start={period_start_rooms}, end={period_end_rooms}, rate={occupancy_rate:.2%}")
    
    return len(target_dates)


def main():
    """Main KPI updater workflow."""
    start_time = datetime.now()
    
    try:
        print("="*60)
        print("OCCUPANCY KPI UPDATER STARTED")
        print("="*60)
        
        # Parse parameters
        target_date_str = args.get('TARGET_DATE', str(date.today()))
        lookback_days = int(args.get('LOOKBACK_DAYS', 3))
        
        target_date = datetime.strptime(target_date_str, '%Y-%m-%d').date()
        
        print(f"Target date: {target_date}")
        print(f"Lookback window: {lookback_days} days")
        
        # Build list of dates to process (target date + lookback)
        dates_to_process = [
            target_date - timedelta(days=i)
            for i in range(lookback_days + 1)
        ]
        dates_to_process.reverse()  # Process oldest to newest
        
        print(f"Dates to process: {[str(d) for d in dates_to_process]}")
        
        # Connect to Aurora
        connection = get_connection()
        
        try:
            cursor = connection.cursor()
            
            # Ensure KPI table exists
            ensure_kpi_table_exists(cursor)
            connection.commit()
            
            # Compute KPIs
            rows_updated = compute_kpi_for_dates(cursor, dates_to_process)
            connection.commit()
            
            # Calculate duration
            duration = (datetime.now() - start_time).total_seconds()
            
            print(f"\n{'='*60}")
            print("KPI UPDATER COMPLETED SUCCESSFULLY")
            print(f"Duration: {duration:.2f} seconds")
            print(f"Dates processed: {rows_updated}")
            print(f"{'='*60}\n")
            
            job.commit()
            
        finally:
            cursor.close()
            connection.close()
        
    except Exception as e:
        print(f"\nERROR: KPI updater failed: {str(e)}")
        import traceback
        traceback.print_exc()
        job.commit()
        raise


if __name__ == "__main__":
    main()
