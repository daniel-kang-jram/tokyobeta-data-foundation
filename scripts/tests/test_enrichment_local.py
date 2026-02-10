#!/usr/bin/env python3
"""
Local test of LLM nationality enrichment
Tests actual Bedrock API calls with real database data
"""

import sys
sys.path.insert(0, 'glue/scripts')

from nationality_enricher import NationalityEnricher
import os

def main():
    print("="*60)
    print("LOCAL TEST: LLM Nationality Enrichment")
    print("="*60)
    
    # Configuration
    config = {
        'aurora_endpoint': 'tokyobeta-prod-aurora-cluster-public.cluster-cr46qo6y4bbb.ap-northeast-1.rds.amazonaws.com',
        'aurora_database': 'tokyobeta',
        'secret_arn': 'arn:aws:secretsmanager:ap-northeast-1:343881458651:secret:tokyobeta/prod/aurora/credentials-tlWiUd',
        'bedrock_region': 'us-east-1',
        'max_batch_size': 5,  # Test with just 5 records
        'requests_per_second': 5,
        'dry_run': True  # Dry run first (IAM user lacks Bedrock access)
    }
    
    print(f"\nConfiguration:")
    print(f"  Aurora: {config['aurora_endpoint']}")
    print(f"  Database: {config['aurora_database']}")
    print(f"  Bedrock Region: {config['bedrock_region']}")
    print(f"  Max Batch: {config['max_batch_size']}")
    print(f"  Dry Run: {config['dry_run']}")
    
    # Set AWS profile
    os.environ['AWS_PROFILE'] = 'gghouse'
    
    print("\n" + "="*60)
    print("Creating enricher instance...")
    print("="*60)
    
    enricher = NationalityEnricher(**config)
    
    print("\n" + "="*60)
    print("Identifying tenants needing enrichment...")
    print("="*60)
    
    tenants = enricher.identify_tenants_needing_enrichment()
    print(f"\nFound {len(tenants)} tenants:")
    for i, tenant in enumerate(tenants[:5], 1):
        print(f"  {i}. ID={tenant['id']}, Name={tenant['full_name']}, "
              f"Current={tenant['nationality']}, Status={tenant['status']}")
    
    if not tenants:
        print("\n⚠️  No tenants need enrichment!")
        return
    
    print("\n" + "="*60)
    print("Making LLM predictions...")
    print("="*60)
    
    predictions = enricher.batch_predict_nationalities(tenants)
    
    print(f"\nPredictions made: {len(predictions)}")
    for i, pred in enumerate(predictions, 1):
        print(f"\n  {i}. Tenant ID: {pred['tenant_id']}")
        print(f"     Name: {pred['tenant_name']}")
        print(f"     Predicted: {pred['predicted_nationality']}")
        if pred['predicted_nationality']:
            print(f"     ✅ SUCCESS")
        else:
            print(f"     ❌ FAILED: {pred.get('error', 'Unknown error')}")
    
    print("\n" + "="*60)
    print("Saving predictions to database...")
    print("="*60)
    
    saved_count = enricher.save_predictions_to_db(predictions)
    print(f"\n✅ Saved {saved_count} predictions to database")
    
    print("\n" + "="*60)
    print("Verifying results in database...")
    print("="*60)
    
    # Query database to verify
    import pymysql
    username, password = enricher.get_credentials()
    connection = pymysql.connect(
        host=config['aurora_endpoint'],
        user=username,
        password=password,
        database=config['aurora_database'],
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )
    
    try:
        cursor = connection.cursor()
        tenant_ids = [p['tenant_id'] for p in predictions]
        placeholders = ','.join(['%s'] * len(tenant_ids))
        
        cursor.execute(f"""
            SELECT 
                id,
                full_name,
                nationality,
                llm_nationality,
                updated_at
            FROM staging.tenants
            WHERE id IN ({placeholders})
            ORDER BY id
        """, tenant_ids)
        
        results = cursor.fetchall()
        print(f"\nDatabase verification ({len(results)} records):")
        for row in results:
            print(f"\n  Tenant ID: {row['id']}")
            print(f"  Name: {row['full_name']}")
            print(f"  Original: {row['nationality']}")
            print(f"  LLM Predicted: {row['llm_nationality']}")
            print(f"  Updated: {row['updated_at']}")
            
    finally:
        connection.close()
    
    print("\n" + "="*60)
    print("TEST COMPLETED SUCCESSFULLY")
    print("="*60)
    print(f"\nSummary:")
    print(f"  - Identified: {len(tenants)} tenants")
    print(f"  - Predicted: {len([p for p in predictions if p['predicted_nationality']])} successful")
    print(f"  - Failed: {len([p for p in predictions if not p['predicted_nationality']])} failed")
    print(f"  - Saved to DB: {saved_count} records")
    
    return predictions

if __name__ == "__main__":
    try:
        predictions = main()
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
