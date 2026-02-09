"""
One-time migration script to copy data from private Aurora cluster to public Aurora cluster.
This fixes the issue where Glue was writing to private cluster but users were querying public cluster.
"""

import sys
import boto3
import json
import pymysql
from datetime import datetime

def get_credentials(secret_arn):
    """Retrieve Aurora credentials from Secrets Manager."""
    sm = boto3.client('secretsmanager')
    response = sm.get_secret_value(SecretId=secret_arn)
    secret = json.loads(response['SecretString'])
    return secret['username'], secret['password']

def get_connection(endpoint, username, password, database=None):
    """Create MySQL connection."""
    conn_params = {
        'host': endpoint,
        'user': username,
        'password': password,
        'charset': 'utf8mb4',
        'cursorclass': pymysql.cursors.DictCursor
    }
    if database:
        conn_params['database'] = database
    return pymysql.connect(**conn_params)

def copy_schema_and_data(source_conn, dest_conn, schema_name):
    """Copy entire schema and all its data from source to destination."""
    print(f"\n=== Migrating schema: {schema_name} ===")
    
    source_cursor = source_conn.cursor()
    dest_cursor = dest_conn.cursor()
    
    try:
        # Create schema if it doesn't exist
        dest_cursor.execute(f"CREATE SCHEMA IF NOT EXISTS `{schema_name}`")
        dest_conn.commit()
        print(f"✓ Schema '{schema_name}' created/verified")
        
        # Get all tables in source schema
        source_cursor.execute(f"""
            SELECT TABLE_NAME 
            FROM information_schema.TABLES 
            WHERE TABLE_SCHEMA = '{schema_name}'
            AND TABLE_TYPE = 'BASE TABLE'
            ORDER BY TABLE_NAME
        """)
        
        tables = [row['TABLE_NAME'] for row in source_cursor.fetchall()]
        print(f"Found {len(tables)} tables to migrate")
        
        for table_name in tables:
            print(f"\n  Migrating {schema_name}.{table_name}...")
            
            # Set database context for both connections
            source_cursor.execute(f"USE `{schema_name}`")
            dest_cursor.execute(f"USE `{schema_name}`")
            
            # Get CREATE TABLE statement
            source_cursor.execute(f"SHOW CREATE TABLE `{table_name}`")
            create_stmt = source_cursor.fetchone()['Create Table']
            
            # Drop and recreate table in destination
            dest_cursor.execute(f"DROP TABLE IF EXISTS `{table_name}`")
            dest_cursor.execute(create_stmt)
            dest_conn.commit()
            print(f"    ✓ Table structure created")
            
            # Count rows in source
            source_cursor.execute(f"SELECT COUNT(*) as cnt FROM `{table_name}`")
            row_count = source_cursor.fetchone()['cnt']
            
            if row_count == 0:
                print(f"    ⊘ Table is empty, skipping data copy")
                continue
            
            print(f"    Copying {row_count:,} rows...")
            
            # Copy data in batches (10,000 rows at a time)
            batch_size = 10000
            offset = 0
            
            while offset < row_count:
                # Fetch batch from source
                source_cursor.execute(f"""
                    SELECT * FROM `{table_name}` 
                    LIMIT {batch_size} OFFSET {offset}
                """)
                
                rows = source_cursor.fetchall()
                if not rows:
                    break
                
                # Get column names
                columns = list(rows[0].keys())
                column_list = ", ".join([f"`{col}`" for col in columns])
                placeholders = ", ".join(["%s"] * len(columns))
                
                # Insert into destination
                insert_sql = f"""
                    INSERT INTO `{table_name}` ({column_list})
                    VALUES ({placeholders})
                """
                
                values = [tuple(row.values()) for row in rows]
                dest_cursor.executemany(insert_sql, values)
                dest_conn.commit()
                
                offset += len(rows)
                progress = (offset / row_count) * 100
                print(f"      Progress: {offset:,}/{row_count:,} ({progress:.1f}%)")
            
            print(f"    ✓ {row_count:,} rows copied successfully")
        
        print(f"\n✓ Schema '{schema_name}' migration complete!")
        return len(tables)
        
    except Exception as e:
        print(f"✗ Error migrating {schema_name}: {str(e)}")
        raise
    finally:
        source_cursor.close()
        dest_cursor.close()

def main():
    """Main migration workflow."""
    print("="*60)
    print("AURORA CLUSTER DATA MIGRATION")
    print(f"Started: {datetime.now()}")
    print("="*60)
    
    # Configuration
    SECRET_ARN = "arn:aws:secretsmanager:ap-northeast-1:343881458651:secret:tokyobeta/prod/aurora/credentials-tlWiUd"
    SOURCE_ENDPOINT = "tokyobeta-prod-aurora-cluster.cluster-cr46qo6y4bbb.ap-northeast-1.rds.amazonaws.com"
    DEST_ENDPOINT = "tokyobeta-prod-aurora-cluster-public.cluster-cr46qo6y4bbb.ap-northeast-1.rds.amazonaws.com"
    
    SCHEMAS_TO_MIGRATE = ['staging', 'silver', 'gold', 'seeds']
    
    try:
        # Get credentials
        print("\nRetrieving credentials...")
        username, password = get_credentials(SECRET_ARN)
        print("✓ Credentials retrieved")
        
        # Connect to both clusters
        print(f"\nConnecting to SOURCE: {SOURCE_ENDPOINT}")
        source_conn = get_connection(SOURCE_ENDPOINT, username, password)
        print("✓ Connected to source cluster")
        
        print(f"\nConnecting to DESTINATION: {DEST_ENDPOINT}")
        dest_conn = get_connection(DEST_ENDPOINT, username, password)
        print("✓ Connected to destination cluster")
        
        # Migrate each schema
        total_tables = 0
        for schema in SCHEMAS_TO_MIGRATE:
            tables_migrated = copy_schema_and_data(source_conn, dest_conn, schema)
            total_tables += tables_migrated
        
        # Close connections
        source_conn.close()
        dest_conn.close()
        
        # Success summary
        duration = datetime.now()
        print("\n" + "="*60)
        print("MIGRATION COMPLETE!")
        print(f"Completed: {duration}")
        print(f"Total schemas migrated: {len(SCHEMAS_TO_MIGRATE)}")
        print(f"Total tables migrated: {total_tables}")
        print("="*60)
        
    except Exception as e:
        print(f"\n✗ MIGRATION FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
