"""
Lambda function to trigger AWS Glue ETL job from EventBridge.
This is a lightweight wrapper since EventBridge can't trigger Glue jobs directly.
"""

import boto3
import os

glue = boto3.client('glue')

def handler(event, context):
    """Start the Glue ETL job."""
    job_name = os.environ['GLUE_JOB_NAME']
    
    response = glue.start_job_run(
        JobName=job_name
    )
    
    return {
        'statusCode': 200,
        'body': {
            'message': f'Started Glue job: {job_name}',
            'jobRunId': response['JobRunId']
        }
    }
