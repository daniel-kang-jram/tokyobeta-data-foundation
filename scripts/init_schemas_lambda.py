"""
Lambda function to initialize Aurora database schemas.
Run this once after Aurora is deployed.
"""

import boto3
import json
import pymysql

secretsmanager = boto3.client('secretsmanager', region_name='ap-northeast-1')

def lambda_handler(event, context):
    # Get Aurora credentials
    secret_arn = "arn:aws:secretsmanager:ap-northeast-1:343881458651:secret:tokyobeta/prod/aurora/credentials-tlWiUd"
    response = secretsmanager.get_secret_value(SecretId=secret_arn)
    secret = json.loads(response['SecretString'])
    
    # Connect to Aurora
    connection = pymysql.connect(
        host='tokyobeta-prod-aurora-cluster.cluster-cr46qo6y4bbb.ap-northeast-1.rds.amazonaws.com',
        user=secret['username'],
        password=secret['password'],
        database='tokyobeta'
    )
    
    try:
        cursor = connection.cursor()
        
        # Create schemas
        schemas_sql = """
        CREATE SCHEMA IF NOT EXISTS staging;
        CREATE SCHEMA IF NOT EXISTS analytics;
        CREATE SCHEMA IF NOT EXISTS seeds;
        """
        
        for stmt in schemas_sql.strip().split(';'):
            if stmt.strip():
                cursor.execute(stmt)
        
        connection.commit()
        
        # Verify
        cursor.execute("SHOW SCHEMAS")
        schemas = [row[0] for row in cursor.fetchall()]
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Schemas created successfully',
                'schemas': schemas
            })
        }
        
    finally:
        cursor.close()
        connection.close()

# For local testing
if __name__ == "__main__":
    result = lambda_handler({}, {})
    print(json.dumps(result, indent=2))
