"""
Nationality Enricher - AWS Bedrock LLM-powered nationality prediction

Enriches tenant records with missing/placeholder nationality data by:
1. Identifying tenants with レソト placeholder, NULL, or empty nationality
2. Using AWS Bedrock (Claude 3 Haiku) to predict nationality from names
3. Updating staging.tenants with llm_nationality column

This runs between staging_loader and dbt transformations.
"""

import sys
import boto3
import json
import pymysql
import time
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)


class NationalityEnricher:
    """Enriches tenant nationality data using AWS Bedrock LLM predictions."""
    
    # Claude 3 Haiku model (fast, cost-effective for name-based prediction)
    BEDROCK_MODEL_ID = 'anthropic.claude-3-haiku-20240307-v1:0'
    
    # Nationality prediction prompt template
    NATIONALITY_PREDICTION_PROMPT = """Based on this person's name, predict their most likely nationality.

Name: {name}

Instructions:
- Respond with ONLY the nationality in Japanese (e.g., 日本, 中国, ベトナム, ミャンマー, etc.)
- Use the same format as Japanese government forms
- If the name has clear Japanese kanji/hiragana, respond with: 日本
- If the name has Chinese characters, respond with: 中国 or 台湾
- If the name appears to be from Myanmar/Burma, respond with: ミャンマー
- If the name appears to be from Vietnam, respond with: ベトナム
- If the name appears to be from Mongolia, respond with: モンゴル
- If the name appears to be from Korea, respond with: 韓国
- If truly ambiguous, respond with: その他

Respond with ONLY the nationality, nothing else."""
    
    def __init__(
        self,
        aurora_endpoint: str,
        aurora_database: str,
        secret_arn: str,
        bedrock_region: str = 'us-east-1',
        max_batch_size: int = 1000,
        requests_per_second: int = 5,
        dry_run: bool = False,
        log_every: int = 50
    ):
        """
        Initialize nationality enricher.
        
        Args:
            aurora_endpoint: Aurora cluster endpoint
            aurora_database: Database name
            secret_arn: Secrets Manager ARN for Aurora credentials
            bedrock_region: AWS region for Bedrock API
            max_batch_size: Maximum records to process per run
            requests_per_second: Bedrock API rate limit
            dry_run: If True, predict but don't update database
            log_every: Log progress every N records
        """
        # Validate required parameters
        if not aurora_endpoint:
            raise ValueError("Aurora endpoint required")
        if not bedrock_region:
            raise ValueError("Bedrock region required")
        
        self.aurora_endpoint = aurora_endpoint
        self.aurora_database = aurora_database
        self.secret_arn = secret_arn
        self.bedrock_region = bedrock_region
        self.max_batch_size = max_batch_size
        self.requests_per_second = requests_per_second
        self.dry_run = dry_run
        self.log_every = log_every
        
        # Rate limiting: seconds between requests
        self.request_delay = 1.0 / requests_per_second if requests_per_second > 0 else 0
        
        # Initialize AWS clients
        self.secrets_manager = boto3.client('secretsmanager')
        self.bedrock_client = boto3.client('bedrock-runtime', region_name=bedrock_region)
        
        logger.info(f"NationalityEnricher initialized:")
        logger.info(f"  Aurora: {aurora_endpoint}/{aurora_database}")
        logger.info(f"  Bedrock region: {bedrock_region}")
        logger.info(f"  Model: {self.BEDROCK_MODEL_ID}")
        logger.info(f"  Max batch size: {max_batch_size}")
        logger.info(f"  Rate limit: {requests_per_second} req/s")
        logger.info(f"  Dry run: {dry_run}")
    
    def get_credentials(self) -> Tuple[str, str]:
        """Retrieve Aurora credentials from Secrets Manager."""
        response = self.secrets_manager.get_secret_value(SecretId=self.secret_arn)
        secret = json.loads(response['SecretString'])
        return secret['username'], secret['password']
    
    def get_connection(self) -> pymysql.Connection:
        """Create MySQL connection to Aurora."""
        username, password = self.get_credentials()
        
        return pymysql.connect(
            host=self.aurora_endpoint,
            user=username,
            password=password,
            database=self.aurora_database,
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
    
    def ensure_llm_nationality_column_exists(self):
        """Create llm_nationality column in staging.tenants if it doesn't exist."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            logger.info("Ensuring llm_nationality column exists in staging.tenants...")
            
            # Check if column exists
            cursor.execute("""
                SELECT COUNT(*) as col_exists
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = 'staging'
                  AND TABLE_NAME = 'tenants'
                  AND COLUMN_NAME = 'llm_nationality'
            """)
            
            result = cursor.fetchone()
            
            if result['col_exists'] == 0:
                logger.info("Column doesn't exist, creating...")
                cursor.execute("""
                    ALTER TABLE staging.tenants
                    ADD COLUMN llm_nationality VARCHAR(128) NULL
                    COMMENT 'LLM-predicted nationality for records with missing data'
                """)
                conn.commit()
                logger.info("✓ llm_nationality column created")
            else:
                logger.info("✓ llm_nationality column already exists")
        
        finally:
            cursor.close()
            conn.close()
    
    def identify_tenants_needing_enrichment(self) -> List[Dict]:
        """
        Identify tenants with missing/placeholder nationality data.
        
        Returns:
            List of tenant dicts with id, full_name, nationality, status
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            logger.info("Identifying tenants needing nationality enrichment...")
            
            # Query for tenants with:
            # 1. レソト placeholder (m_nationality_id = 200)
            # 2. NULL nationality
            # 3. Empty string nationality
            # Prioritize active residents (status 9, 11, 14, 15, 16)
            cursor.execute(f"""
                SELECT 
                    id,
                    full_name,
                    nationality,
                    m_nationality_id,
                    status
                FROM staging.tenants
                WHERE (
                    nationality = 'レソト'
                    OR nationality IS NULL
                    OR nationality = ''
                )
                AND llm_nationality IS NULL  -- Don't re-process already enriched
                ORDER BY 
                    -- Prioritize active residents
                    CASE 
                        WHEN status IN (9, 11, 14, 15, 16) THEN 0
                        ELSE 1
                    END,
                    updated_at DESC
                LIMIT {self.max_batch_size}
            """)
            
            tenants = cursor.fetchall()
            
            logger.info(f"Found {len(tenants)} tenants needing enrichment")
            logger.info(f"  - Active residents: {sum(1 for t in tenants if t['status'] in (9, 11, 14, 15, 16))}")
            logger.info(f"  - レソト placeholder: {sum(1 for t in tenants if t['nationality'] == 'レソト')}")
            logger.info(f"  - NULL nationality: {sum(1 for t in tenants if t['nationality'] is None)}")
            logger.info(f"  - Empty nationality: {sum(1 for t in tenants if t['nationality'] == '')}")
            
            return tenants
        
        finally:
            cursor.close()
            conn.close()
    
    def predict_nationality(self, full_name: str) -> Optional[str]:
        """
        Predict nationality from person's name using AWS Bedrock.
        
        Args:
            full_name: Tenant's full name
            
        Returns:
            Predicted nationality in Japanese (e.g., '日本', 'ミャンマー')
            or None if prediction fails
        """
        if not full_name or full_name.strip() == '':
            logger.warning("Empty name provided, cannot predict")
            return 'その他'
        
        try:
            # Construct prompt
            prompt = self.NATIONALITY_PREDICTION_PROMPT.format(name=full_name)
            
            # Prepare request body for Claude 3
            request_body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 50,  # We only need a short response
                "temperature": 0.1,  # Low temperature for more deterministic output
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            }
            
            # Call Bedrock
            response = self.bedrock_client.invoke_model(
                modelId=self.BEDROCK_MODEL_ID,
                body=json.dumps(request_body)
            )
            
            # Parse response
            response_body = json.loads(response['body'].read())
            predicted_nationality = response_body['content'][0]['text'].strip()
            
            logger.debug(f"Predicted '{predicted_nationality}' for name '{full_name}'")
            return predicted_nationality
        
        except Exception as e:
            logger.error(f"Bedrock API error for name '{full_name}': {str(e)}")
            return None
    
    def batch_predict_nationalities(self, tenants: List[Dict]) -> List[Dict]:
        """
        Predict nationalities for a batch of tenants.
        
        Args:
            tenants: List of tenant dicts with id and full_name
            
        Returns:
            List of prediction dicts with tenant_id, predicted_nationality, model_used
        """
        logger.info(f"Starting batch prediction for {len(tenants)} tenants...")
        
        predictions = []
        start_time = time.time()
        
        for idx, tenant in enumerate(tenants, 1):
            # Rate limiting
            if idx > 1 and self.request_delay > 0:
                time.sleep(self.request_delay)
            
            # Predict
            predicted_nationality = self.predict_nationality(tenant['full_name'])
            
            predictions.append({
                'tenant_id': tenant['id'],
                'predicted_nationality': predicted_nationality,
                'model_used': self.BEDROCK_MODEL_ID,
                'original_nationality': tenant.get('nationality'),
                'original_name': tenant.get('full_name')
            })
            
            # Log progress
            if idx % self.log_every == 0 or idx == len(tenants):
                elapsed = time.time() - start_time
                rate = idx / elapsed if elapsed > 0 else 0
                logger.info(f"Progress: {idx}/{len(tenants)} predictions ({rate:.1f} req/s)")
        
        elapsed_total = time.time() - start_time
        logger.info(f"Batch prediction complete in {elapsed_total:.1f}s")
        logger.info(f"  - Successful predictions: {sum(1 for p in predictions if p['predicted_nationality'] is not None)}")
        logger.info(f"  - Failed predictions: {sum(1 for p in predictions if p['predicted_nationality'] is None)}")
        
        return predictions
    
    def save_predictions(self, predictions: List[Dict]):
        """
        Save predictions to staging.tenants table.
        
        Args:
            predictions: List of prediction dicts with tenant_id and predicted_nationality
        """
        if self.dry_run:
            logger.info("DRY RUN: Would save predictions, but dry_run=True")
            for pred in predictions[:5]:  # Show first 5
                logger.info(f"  Would update tenant {pred['tenant_id']}: {pred['predicted_nationality']}")
            return
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        successful_updates = 0
        failed_updates = 0
        
        try:
            logger.info(f"Saving {len(predictions)} predictions to database...")
            
            for pred in predictions:
                try:
                    if pred['predicted_nationality'] is None:
                        # Skip failed predictions
                        continue
                    
                    cursor.execute("""
                        UPDATE staging.tenants
                        SET llm_nationality = %s
                        WHERE id = %s
                    """, (pred['predicted_nationality'], pred['tenant_id']))
                    
                    successful_updates += 1
                
                except Exception as e:
                    logger.error(f"Failed to update tenant {pred['tenant_id']}: {str(e)}")
                    failed_updates += 1
            
            # Commit all updates
            conn.commit()
            
            logger.info(f"✓ Saved {successful_updates} predictions")
            if failed_updates > 0:
                logger.warning(f"⚠ {failed_updates} updates failed")
        
        except Exception as e:
            logger.error(f"Database transaction error: {str(e)}")
            conn.rollback()
            raise
        
        finally:
            cursor.close()
            conn.close()
    
    def enrich_all_missing_nationalities(self) -> Dict:
        """
        Complete enrichment workflow: identify, predict, save.
        
        Returns:
            Summary dict with statistics
        """
        start_time = time.time()
        
        logger.info("="*60)
        logger.info("NATIONALITY ENRICHMENT WORKFLOW START")
        logger.info(f"Timestamp: {datetime.now()}")
        logger.info("="*60)
        
        summary = {
            'tenants_identified': 0,
            'predictions_made': 0,
            'successful_updates': 0,
            'failed_updates': 0,
            'execution_time_seconds': 0
        }
        
        try:
            # Step 1: Ensure schema exists
            self.ensure_llm_nationality_column_exists()
            
            # Step 2: Identify tenants needing enrichment
            tenants = self.identify_tenants_needing_enrichment()
            summary['tenants_identified'] = len(tenants)
            
            if len(tenants) == 0:
                logger.info("No tenants need enrichment. Exiting.")
                return summary
            
            # Step 3: Batch predict nationalities
            predictions = self.batch_predict_nationalities(tenants)
            summary['predictions_made'] = len([p for p in predictions if p['predicted_nationality'] is not None])
            
            # Step 4: Save predictions to database
            self.save_predictions(predictions)
            summary['successful_updates'] = sum(1 for p in predictions if p['predicted_nationality'] is not None)
            summary['failed_updates'] = sum(1 for p in predictions if p['predicted_nationality'] is None)
            
            # Calculate execution time
            summary['execution_time_seconds'] = time.time() - start_time
            
            logger.info("="*60)
            logger.info("NATIONALITY ENRICHMENT COMPLETE")
            logger.info(f"  Tenants identified: {summary['tenants_identified']}")
            logger.info(f"  Predictions made: {summary['predictions_made']}")
            logger.info(f"  Successful updates: {summary['successful_updates']}")
            logger.info(f"  Failed updates: {summary['failed_updates']}")
            logger.info(f"  Execution time: {summary['execution_time_seconds']:.1f}s")
            logger.info("="*60)
            
            return summary
        
        except Exception as e:
            logger.error(f"Enrichment workflow failed: {str(e)}")
            import traceback
            traceback.print_exc()
            raise


def handler(event, context):
    """
    AWS Glue job handler for nationality enrichment.
    
    Environment variables:
        AURORA_ENDPOINT: Aurora cluster endpoint
        AURORA_DATABASE: Database name (default: tokyobeta)
        SECRET_ARN: Secrets Manager ARN
        BEDROCK_REGION: Bedrock API region (default: us-east-1)
        MAX_BATCH_SIZE: Maximum records per run (default: 1000)
        REQUESTS_PER_SECOND: Bedrock rate limit (default: 5)
        DRY_RUN: Set to 'true' for dry run (default: false)
    """
    import os
    
    # Get configuration from environment or event
    config = {
        'aurora_endpoint': os.environ.get('AURORA_ENDPOINT', event.get('aurora_endpoint')),
        'aurora_database': os.environ.get('AURORA_DATABASE', event.get('aurora_database', 'tokyobeta')),
        'secret_arn': os.environ.get('SECRET_ARN', event.get('secret_arn')),
        'bedrock_region': os.environ.get('BEDROCK_REGION', event.get('bedrock_region', 'us-east-1')),
        'max_batch_size': int(os.environ.get('MAX_BATCH_SIZE', event.get('max_batch_size', 1000))),
        'requests_per_second': int(os.environ.get('REQUESTS_PER_SECOND', event.get('requests_per_second', 5))),
        'dry_run': os.environ.get('DRY_RUN', event.get('dry_run', 'false')).lower() == 'true'
    }
    
    # Validate required parameters
    if not config['aurora_endpoint'] or not config['secret_arn']:
        raise ValueError("aurora_endpoint and secret_arn are required")
    
    # Create enricher and run
    enricher = NationalityEnricher(**config)
    summary = enricher.enrich_all_missing_nationalities()
    
    return {
        'statusCode': 200,
        'body': json.dumps(summary),
        'summary': summary
    }


if __name__ == "__main__":
    """Local testing entry point."""
    # For local testing, load config from command line args or defaults
    import argparse
    
    parser = argparse.ArgumentParser(description='Enrich tenant nationality data using AWS Bedrock')
    parser.add_argument('--endpoint', required=True, help='Aurora cluster endpoint')
    parser.add_argument('--database', default='tokyobeta', help='Database name')
    parser.add_argument('--secret-arn', required=True, help='Secrets Manager ARN')
    parser.add_argument('--bedrock-region', default='us-east-1', help='Bedrock region')
    parser.add_argument('--max-batch', type=int, default=1000, help='Max batch size')
    parser.add_argument('--rate-limit', type=int, default=5, help='Requests per second')
    parser.add_argument('--dry-run', action='store_true', help='Predict but don\'t update')
    
    args = parser.parse_args()
    
    enricher = NationalityEnricher(
        aurora_endpoint=args.endpoint,
        aurora_database=args.database,
        secret_arn=args.secret_arn,
        bedrock_region=args.bedrock_region,
        max_batch_size=args.max_batch,
        requests_per_second=args.rate_limit,
        dry_run=args.dry_run
    )
    
    summary = enricher.enrich_all_missing_nationalities()
    print(json.dumps(summary, indent=2))
