#!/usr/bin/env python3
"""
Standalone Nationality Enrichment Script
Run ONLY the nationality enrichment without full ETL
"""

import sys
import boto3
import os
import tempfile

# Configuration
AURORA_ENDPOINT = "tokyobeta-prod-aurora-cluster-public.cluster-cr46qo6y4bbb.ap-northeast-1.rds.amazonaws.com"
AURORA_DATABASE = "tokyobeta"
SECRET_ARN = "arn:aws:secretsmanager:ap-northeast-1:343881458651:secret:tokyobeta/prod/aurora/credentials-tlWiUd"
S3_BUCKET = "jram-gghouse"
BEDROCK_REGION = "us-east-1"

def main():
    print("="*60)
    print("Standalone Nationality Enrichment")
    print("="*60)
    print()
    
    # Download nationality_enricher.py from S3
    print("Downloading nationality_enricher.py from S3...")
    s3 = boto3.client('s3', region_name='ap-northeast-1')
    enricher_path = os.path.join(tempfile.gettempdir(), 'nationality_enricher.py')
    
    s3.download_file(
        S3_BUCKET,
        'glue-scripts/nationality_enricher.py',
        enricher_path
    )
    
    # Add to Python path
    enricher_dir = os.path.dirname(enricher_path)
    if enricher_dir not in sys.path:
        sys.path.insert(0, enricher_dir)
    
    print(f"✓ Downloaded to: {enricher_path}")
    print()
    
    # Import enricher
    from nationality_enricher import NationalityEnricher
    
    # Create enricher instance
    print("Initializing enricher...")
    enricher = NationalityEnricher(
        aurora_endpoint=AURORA_ENDPOINT,
        aurora_database=AURORA_DATABASE,
        secret_arn=SECRET_ARN,
        bedrock_region=BEDROCK_REGION,
        max_batch_size=1000,
        requests_per_second=5,
        dry_run=False
    )
    
    print("✓ Enricher initialized")
    print()
    
    # Run enrichment
    print("Starting enrichment...")
    print("-" * 60)
    summary = enricher.enrich_all_missing_nationalities()
    
    # Print results
    print()
    print("="*60)
    print("✓ Enrichment Complete!")
    print("="*60)
    print(f"Tenants identified:   {summary['tenants_identified']}")
    print(f"Predictions made:     {summary['predictions_made']}")
    print(f"Successful updates:   {summary['successful_updates']}")
    print(f"Failed updates:       {summary['failed_updates']}")
    print(f"Execution time:       {summary['execution_time_seconds']:.1f}s")
    print("="*60)
    
    # Show verification query
    print()
    print("Verify results in database:")
    print("  SELECT COUNT(*) FROM staging.tenants WHERE llm_nationality IS NOT NULL;")
    print()

if __name__ == "__main__":
    main()
