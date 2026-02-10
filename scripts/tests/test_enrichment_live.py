#!/usr/bin/env python3
"""
Live test of nationality enrichment against real Aurora database and Bedrock API.
Tests a small sample (5 records) in dry-run mode.
"""

import sys
sys.path.insert(0, '/Users/danielkang/tokyobeta-data-consolidation/glue/scripts')

from nationality_enricher import NationalityEnricher

def main():
    print("="*60)
    print("LIVE TEST: Nationality Enrichment")
    print("="*60)
    print()
    
    # Configuration
    config = {
        'aurora_endpoint': 'tokyobeta-prod-aurora-cluster-public.cluster-cr46qo6y4bbb.ap-northeast-1.rds.amazonaws.com',
        'aurora_database': 'tokyobeta',
        'secret_arn': 'arn:aws:secretsmanager:ap-northeast-1:343881458651:secret:tokyobeta/prod/aurora/credentials-tlWiUd',
        'bedrock_region': 'us-east-1',
        'max_batch_size': 5,  # Test with just 5 records
        'requests_per_second': 2,  # Slow down for testing
        'dry_run': True  # Don't update database (safe test)
    }
    
    print("Configuration:")
    print(f"  Aurora: {config['aurora_endpoint']}")
    print(f"  Database: {config['aurora_database']}")
    print(f"  Bedrock Region: {config['bedrock_region']}")
    print(f"  Max Batch: {config['max_batch_size']}")
    print(f"  Dry Run: {config['dry_run']}")
    print()
    
    # Create enricher
    enricher = NationalityEnricher(**config)
    
    # Run enrichment
    print("Running enrichment...")
    print()
    
    try:
        summary = enricher.enrich_all_missing_nationalities()
        
        print()
        print("="*60)
        print("✓ TEST SUCCESSFUL")
        print("="*60)
        print(f"Tenants identified: {summary['tenants_identified']}")
        print(f"Predictions made: {summary['predictions_made']}")
        print(f"Successful updates: {summary['successful_updates']} (dry-run, not actually updated)")
        print(f"Failed updates: {summary['failed_updates']}")
        print(f"Execution time: {summary['execution_time_seconds']:.2f}s")
        print()
        print("Next steps:")
        print("  1. Review predictions above")
        print("  2. If accurate, deploy to AWS (see DEPLOYMENT_READY.md)")
        print("  3. Run with dry_run=False to actually update database")
        
        return 0
        
    except Exception as e:
        print()
        print("="*60)
        print("✗ TEST FAILED")
        print("="*60)
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
