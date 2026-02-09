#!/usr/bin/env python3
"""
Live test of nationality enrichment with direct DB credentials.
Tests against real Aurora database and Bedrock API.
"""

import sys
import boto3
import pymysql
import json
from datetime import datetime

# Configuration
AURORA_ENDPOINT = 'tokyobeta-prod-aurora-cluster-public.cluster-cr46qo6y4bbb.ap-northeast-1.rds.amazonaws.com'
AURORA_DATABASE = 'tokyobeta'
AURORA_USERNAME = 'admin'
AURORA_PASSWORD = 'K6ghcWTq4p-zlidRJ2<AJX<w$zN<a8dU'
BEDROCK_MODEL = 'anthropic.claude-3-haiku-20240307-v1:0'  # Claude 3 Haiku (base model, directly accessible)
MAX_SAMPLES = 5

def test_database_connection():
    """Test Aurora connection."""
    print("Testing database connection...")
    try:
        conn = pymysql.connect(
            host=AURORA_ENDPOINT,
            user=AURORA_USERNAME,
            password=AURORA_PASSWORD,
            database=AURORA_DATABASE,
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM staging.tenants WHERE llm_nationality IS NULL AND (nationality = 'レソト' OR nationality IS NULL OR nationality = '')")
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        print(f"✓ Database connection successful")
        print(f"  Found {result['count']:,} tenants needing enrichment")
        return True
    except Exception as e:
        print(f"✗ Database connection failed: {e}")
        return False

def get_sample_tenants():
    """Get sample tenants for testing."""
    print(f"\nFetching {MAX_SAMPLES} sample tenants...")
    conn = pymysql.connect(
        host=AURORA_ENDPOINT,
        user=AURORA_USERNAME,
        password=AURORA_PASSWORD,
        database=AURORA_DATABASE,
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )
    cursor = conn.cursor()
    
    cursor.execute(f"""
        SELECT 
            id,
            full_name,
            nationality,
            m_nationality_id,
            status
        FROM staging.tenants
        WHERE llm_nationality IS NULL 
          AND (nationality = 'レソト' OR nationality IS NULL OR nationality = '')
        ORDER BY 
            CASE WHEN status IN (9, 11, 14, 15, 16) THEN 0 ELSE 1 END,
            updated_at DESC
        LIMIT {MAX_SAMPLES}
    """)
    
    tenants = cursor.fetchall()
    cursor.close()
    conn.close()
    
    print(f"✓ Retrieved {len(tenants)} tenants:")
    for t in tenants:
        nat = t['nationality'] if t['nationality'] else 'NULL'
        if nat == '':
            nat = 'EMPTY'
        print(f"  - ID {t['id']}: {t['full_name'][:30]:30} | {nat}")
    
    return tenants

def predict_nationality(bedrock_client, name):
    """Predict nationality using Bedrock."""
    prompt = f"""Based on this person's name, predict their most likely nationality.

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
    
    request_body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 50,
        "temperature": 0.1,
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ]
    }
    
    response = bedrock_client.invoke_model(
        modelId=BEDROCK_MODEL,
        body=json.dumps(request_body)
    )
    
    response_body = json.loads(response['body'].read())
    return response_body['content'][0]['text'].strip()

def test_bedrock_predictions(tenants):
    """Test Bedrock API predictions."""
    print(f"\nTesting Bedrock API predictions...")
    print(f"Model: {BEDROCK_MODEL}")
    print()
    
    bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')
    
    predictions = []
    for i, tenant in enumerate(tenants, 1):
        try:
            print(f"[{i}/{len(tenants)}] Predicting for: {tenant['full_name']}")
            prediction = predict_nationality(bedrock, tenant['full_name'])
            predictions.append({
                'tenant_id': tenant['id'],
                'name': tenant['full_name'],
                'original': tenant['nationality'],
                'predicted': prediction
            })
            print(f"         → Predicted: {prediction}")
        except Exception as e:
            print(f"         ✗ Error: {e}")
            predictions.append({
                'tenant_id': tenant['id'],
                'name': tenant['full_name'],
                'original': tenant['nationality'],
                'predicted': None,
                'error': str(e)
            })
    
    return predictions

def main():
    print("="*60)
    print("LIVE TEST: LLM Nationality Enrichment")
    print("="*60)
    print(f"Started: {datetime.now()}")
    print()
    
    # Step 1: Test database connection
    if not test_database_connection():
        return 1
    
    # Step 2: Get sample tenants
    try:
        tenants = get_sample_tenants()
        if len(tenants) == 0:
            print("\n✓ No tenants need enrichment (all are already enriched)")
            return 0
    except Exception as e:
        print(f"\n✗ Failed to fetch tenants: {e}")
        return 1
    
    # Step 3: Test Bedrock predictions
    try:
        predictions = test_bedrock_predictions(tenants)
    except Exception as e:
        print(f"\n✗ Bedrock API test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    # Summary
    print()
    print("="*60)
    print("✓ TEST COMPLETE")
    print("="*60)
    print(f"Tenants tested: {len(tenants)}")
    print(f"Successful predictions: {sum(1 for p in predictions if p.get('predicted'))}")
    print(f"Failed predictions: {sum(1 for p in predictions if not p.get('predicted'))}")
    print()
    print("Sample Predictions:")
    for p in predictions[:5]:
        orig = p['original'] if p['original'] else 'NULL'
        if orig == '':
            orig = 'EMPTY'
        pred = p.get('predicted', 'ERROR')
        print(f"  {p['name'][:30]:30} | {orig:10} → {pred}")
    print()
    print("NOTE: This was a DRY RUN - database was NOT updated")
    print("To actually update, deploy to AWS Glue (see DEPLOYMENT_READY.md)")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
