"""
Lambda function to refresh QuickSight SPICE datasets
Triggered daily by CloudWatch Events after ETL completion
"""

import json
import os
import boto3
from datetime import datetime

quicksight = boto3.client('quicksight')

def handler(event, context):
    """
    Refresh specified QuickSight SPICE datasets
    
    Environment variables:
        QUICKSIGHT_AWS_ACCOUNT_ID: AWS account ID
        QUICKSIGHT_DATASET_IDS: Comma-separated dataset IDs to refresh
    """
    account_id = os.environ['QUICKSIGHT_AWS_ACCOUNT_ID']
    dataset_ids_str = os.environ.get('QUICKSIGHT_DATASET_IDS', '')
    
    if not dataset_ids_str:
        print("No dataset IDs configured, skipping refresh")
        return {
            'statusCode': 200,
            'body': json.dumps({'message': 'No datasets to refresh'})
        }
    
    dataset_ids = [ds.strip() for ds in dataset_ids_str.split(',') if ds.strip()]
    
    print(f"Refreshing {len(dataset_ids)} datasets: {dataset_ids}")
    
    results = []
    errors = []
    
    for dataset_id in dataset_ids:
        try:
            print(f"Starting ingestion for dataset: {dataset_id}")
            
            ingestion_id = f"refresh-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
            
            response = quicksight.create_ingestion(
                AwsAccountId=account_id,
                DataSetId=dataset_id,
                IngestionId=ingestion_id
            )
            
            results.append({
                'dataset_id': dataset_id,
                'ingestion_id': ingestion_id,
                'status': 'INITIATED',
                'arn': response.get('Arn')
            })
            
            print(f"✅ Ingestion initiated for {dataset_id}: {ingestion_id}")
            
        except Exception as e:
            error_msg = f"Failed to refresh dataset {dataset_id}: {str(e)}"
            print(f"❌ {error_msg}")
            errors.append({
                'dataset_id': dataset_id,
                'error': str(e)
            })
    
    response_body = {
        'message': f'Refreshed {len(results)} datasets',
        'timestamp': datetime.utcnow().isoformat(),
        'results': results,
        'errors': errors
    }
    
    # Return error status if any refreshes failed
    status_code = 200 if not errors else 207  # 207 = Multi-Status
    
    print(f"Refresh complete: {len(results)} succeeded, {len(errors)} failed")
    
    return {
        'statusCode': status_code,
        'body': json.dumps(response_body)
    }
