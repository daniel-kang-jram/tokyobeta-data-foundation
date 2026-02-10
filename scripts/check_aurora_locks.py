#!/usr/bin/env python3
"""Check Aurora process list for locks."""

import pymysql
import boto3
import json

DB_SECRET_ARN = 'arn:aws:secretsmanager:ap-northeast-1:343881458651:secret:tokyobeta/prod/aurora/credentials-tlWiUd'
REGION = 'ap-northeast-1'
DB_HOST = 'tokyobeta-prod-aurora-cluster-public.cluster-cr46qo6y4bbb.ap-northeast-1.rds.amazonaws.com'


def get_db_connection():
    session = boto3.session.Session()
    client = session.client(service_name='secretsmanager', region_name=REGION)
    get_secret_value_response = client.get_secret_value(SecretId=DB_SECRET_ARN)
    secret = json.loads(get_secret_value_response['SecretString'])
    user = secret.get('username') or secret.get('user')
    password = secret.get('password')
    return pymysql.connect(
        host=DB_HOST, user=user, password=password,
        database='tokyobeta', cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=30, read_timeout=30
    )


def main():
    conn = get_db_connection()
    cursor = conn.cursor()

    print("=== SHOW FULL PROCESSLIST ===")
    cursor.execute("SHOW FULL PROCESSLIST")
    for row in cursor.fetchall():
        time = row.get('Time', 0)
        if time and int(time) > 5:  # Show processes running > 5 seconds
            print(f"  ID={row['Id']} User={row['User']} DB={row.get('db')} "
                  f"Time={row['Time']}s State={row.get('State')} "
                  f"Command={row.get('Command')} Info={str(row.get('Info', ''))[:100]}")

    print("\n=== Long-running queries ===")
    cursor.execute("""
        SELECT * FROM information_schema.PROCESSLIST
        WHERE TIME > 10
        ORDER BY TIME DESC
    """)
    for row in cursor.fetchall():
        print(f"  ID={row['ID']} User={row['USER']} DB={row.get('DB')} "
              f"Time={row['TIME']}s State={row.get('STATE')} "
              f"Info={str(row.get('INFO', ''))[:150]}")

    print("\n=== Metadata locks ===")
    try:
        cursor.execute("""
            SELECT * FROM performance_schema.metadata_locks
            WHERE OBJECT_SCHEMA = 'silver'
        """)
        for row in cursor.fetchall():
            print(f"  {row}")
    except Exception as e:
        print(f"  Cannot query metadata_locks: {e}")

    cursor.close()
    conn.close()


if __name__ == "__main__":
    main()
