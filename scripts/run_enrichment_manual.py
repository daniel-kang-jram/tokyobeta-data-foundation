#!/usr/bin/env python3
"""
Manual LLM Enrichment Runner
Runs nationality enrichment on staging.tenants without reloading staging data.
"""

import sys
import os
import argparse
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../glue/scripts'))

from nationality_enricher import NationalityEnricher
import json

# Database configuration
DB_CONFIG = {
    'aurora_endpoint': 'tokyobeta-prod-aurora-cluster-public.cluster-cr46qo6y4bbb.ap-northeast-1.rds.amazonaws.com',
    'aurora_database': 'tokyobeta',
    'secret_arn': 'arn:aws:secretsmanager:ap-northeast-1:343881458651:secret:tokyobeta/prod/aurora/credentials-tlWiUd',
    'bedrock_region': 'us-east-1',
    'max_batch_size': 2500,  # Process all 2,001 target records
    'requests_per_second': 5,
    'dry_run': False  # Set to True to test without actually updating
}

def main():
    parser = argparse.ArgumentParser(description='Manual LLM nationality enrichment')
    parser.add_argument('--yes', '-y', action='store_true', help='Skip confirmation prompt')
    parser.add_argument('--dry-run', action='store_true', help='Run without updating database')
    args = parser.parse_args()
    
    if args.dry_run:
        DB_CONFIG['dry_run'] = True
    
    print("="*70)
    print("MANUAL LLM NATIONALITY ENRICHMENT")
    print("="*70)
    print("")
    print("This will enrich up to 2,500 tenants where:")
    print("  - nationality IS NULL")
    print("  - nationality = '' (empty)")
    print("  - nationality = 'レソト' (placeholder)")
    print("")
    print(f"Configuration:")
    print(f"  Database: {DB_CONFIG['aurora_database']}")
    print(f"  Endpoint: {DB_CONFIG['aurora_endpoint']}")
    print(f"  Max batch: {DB_CONFIG['max_batch_size']}")
    print(f"  Dry run: {DB_CONFIG['dry_run']}")
    print("")
    
    if DB_CONFIG['dry_run']:
        print("⚠️  DRY RUN MODE - No database updates will be made")
    elif not args.yes:
        try:
            response = input("Ready to enrich? This will update staging.tenants. (y/N): ")
            if response.lower() != 'y':
                print("Cancelled.")
                return
        except EOFError:
            print("ERROR: Cannot get user input. Use --yes flag to skip confirmation.")
            sys.exit(1)
    
    print("")
    print("Creating enricher instance...")
    
    try:
        enricher = NationalityEnricher(**DB_CONFIG)
        
        print("Starting enrichment...")
        summary = enricher.enrich_all_missing_nationalities()
        
        print("")
        print("="*70)
        print("ENRICHMENT COMPLETE")
        print("="*70)
        print("")
        print(f"✓ Tenants identified:    {summary['tenants_identified']}")
        print(f"✓ Predictions made:      {summary['predictions_made']}")
        print(f"✓ Successful updates:    {summary['successful_updates']}")
        print(f"✓ Failed updates:        {summary['failed_updates']}")
        print(f"✓ Execution time:        {summary['execution_time_seconds']:.1f}s")
        print("")
        
        if summary['failed_updates'] > 0:
            print("⚠️  Some updates failed. Check logs above for details.")
        
        print("Verify results:")
        print("  mysql> SELECT COUNT(*) FROM staging.tenants WHERE llm_nationality IS NOT NULL;")
        print("")
        
    except Exception as e:
        print("")
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()
