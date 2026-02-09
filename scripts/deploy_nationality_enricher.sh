#!/bin/bash
# Deploy LLM Nationality Enricher to AWS Glue
# Usage: ./scripts/deploy_nationality_enricher.sh [--dry-run]

set -e

# Configuration
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT_PATH="${PROJECT_ROOT}/glue/scripts/nationality_enricher.py"
S3_BUCKET="tokyobeta-etl-artifacts"
S3_KEY="glue/scripts/nationality_enricher.py"
JOB_NAME="tokyobeta-nationality-enricher"
GLUE_ROLE="GlueServiceRole-tokyobeta"
REGION="ap-northeast-1"

# Aurora configuration
AURORA_ENDPOINT="tokyobeta-prod-aurora-cluster-public.cluster-cr46qo6y4bbb.ap-northeast-1.rds.amazonaws.com"
AURORA_DATABASE="tokyobeta"
SECRET_ARN="arn:aws:secretsmanager:ap-northeast-1:343881458651:secret:tokyobeta/prod/aurora/credentials-tlWiUd"
BEDROCK_REGION="us-east-1"

# Default arguments
MAX_BATCH_SIZE="1000"
REQUESTS_PER_SECOND="5"
DRY_RUN="false"

# Check for --dry-run flag
if [[ "$1" == "--dry-run" ]]; then
    DRY_RUN="true"
    echo "🧪 DRY RUN MODE: Will predict but not update database"
fi

echo "=================================================="
echo "LLM Nationality Enricher Deployment"
echo "=================================================="
echo ""

# Step 1: Upload script to S3
echo "Step 1: Uploading script to S3..."
aws s3 cp \
    "${SCRIPT_PATH}" \
    "s3://${S3_BUCKET}/${S3_KEY}" \
    --region "${REGION}"

if [ $? -eq 0 ]; then
    echo "✓ Script uploaded to s3://${S3_BUCKET}/${S3_KEY}"
else
    echo "✗ Failed to upload script to S3"
    exit 1
fi

echo ""

# Step 2: Check if Glue job exists
echo "Step 2: Checking if Glue job exists..."
JOB_EXISTS=$(aws glue get-job \
    --job-name "${JOB_NAME}" \
    --region "${REGION}" \
    2>&1 || echo "not_found")

if [[ "${JOB_EXISTS}" == *"EntityNotFoundException"* ]] || [[ "${JOB_EXISTS}" == "not_found" ]]; then
    echo "Job doesn't exist, creating new job..."
    
    # Create new Glue job
    aws glue create-job \
        --name "${JOB_NAME}" \
        --role "${GLUE_ROLE}" \
        --command '{"Name":"pythonshell","ScriptLocation":"s3://'"${S3_BUCKET}"'/'"${S3_KEY}"'","PythonVersion":"3.9"}' \
        --default-arguments '{
            "library-set":"analytics",
            "--AURORA_ENDPOINT":"'"${AURORA_ENDPOINT}"'",
            "--AURORA_DATABASE":"'"${AURORA_DATABASE}"'",
            "--SECRET_ARN":"'"${SECRET_ARN}"'",
            "--BEDROCK_REGION":"'"${BEDROCK_REGION}"'",
            "--MAX_BATCH_SIZE":"'"${MAX_BATCH_SIZE}"'",
            "--REQUESTS_PER_SECOND":"'"${REQUESTS_PER_SECOND}"'",
            "--DRY_RUN":"'"${DRY_RUN}"'"
        }' \
        --max-capacity 0.0625 \
        --glue-version "3.0" \
        --region "${REGION}" \
        --description "LLM-powered nationality enrichment using AWS Bedrock (Claude 3 Haiku)" \
        --tags '{"Project":"tokyobeta-data-consolidation","Component":"nationality-enricher","ManagedBy":"script"}' \
        --timeout 60

    if [ $? -eq 0 ]; then
        echo "✓ Glue job '${JOB_NAME}' created successfully"
    else
        echo "✗ Failed to create Glue job"
        exit 1
    fi
else
    echo "Job exists, updating..."
    
    # Update existing Glue job
    aws glue update-job \
        --job-name "${JOB_NAME}" \
        --job-update '{
            "Role":"'"${GLUE_ROLE}"'",
            "Command":{
                "Name":"pythonshell",
                "ScriptLocation":"s3://'"${S3_BUCKET}"'/'"${S3_KEY}"'",
                "PythonVersion":"3.9"
            },
            "DefaultArguments":{
                "library-set":"analytics",
                "--AURORA_ENDPOINT":"'"${AURORA_ENDPOINT}"'",
                "--AURORA_DATABASE":"'"${AURORA_DATABASE}"'",
                "--SECRET_ARN":"'"${SECRET_ARN}"'",
                "--BEDROCK_REGION":"'"${BEDROCK_REGION}"'",
                "--MAX_BATCH_SIZE":"'"${MAX_BATCH_SIZE}"'",
                "--REQUESTS_PER_SECOND":"'"${REQUESTS_PER_SECOND}"'",
                "--DRY_RUN":"'"${DRY_RUN}"'"
            },
            "MaxCapacity":0.0625,
            "Timeout":60
        }' \
        --region "${REGION}"

    if [ $? -eq 0 ]; then
        echo "✓ Glue job '${JOB_NAME}' updated successfully"
    else
        echo "✗ Failed to update Glue job"
        exit 1
    fi
fi

echo ""

# Step 3: Check Bedrock permissions
echo "Step 3: Checking Bedrock permissions..."
POLICIES=$(aws iam list-attached-role-policies \
    --role-name "${GLUE_ROLE}" \
    --query 'AttachedPolicies[?PolicyName==`AmazonBedrockFullAccess`]' \
    --output text)

if [ -z "${POLICIES}" ]; then
    echo "⚠ Bedrock permissions not found, attaching policy..."
    aws iam attach-role-policy \
        --role-name "${GLUE_ROLE}" \
        --policy-arn "arn:aws:iam::aws:policy/AmazonBedrockFullAccess"
    
    if [ $? -eq 0 ]; then
        echo "✓ Bedrock permissions attached"
    else
        echo "✗ Failed to attach Bedrock permissions"
        exit 1
    fi
else
    echo "✓ Bedrock permissions already configured"
fi

echo ""

# Step 4: Add database column (if needed)
echo "Step 4: Adding llm_nationality column to database..."
echo "Run this SQL manually against Aurora:"
echo ""
echo "ALTER TABLE staging.tenants"
echo "ADD COLUMN IF NOT EXISTS llm_nationality VARCHAR(128) NULL"
echo "COMMENT 'LLM-predicted nationality for records with missing data';"
echo ""
echo "(Or run: mysql -h ${AURORA_ENDPOINT} -u admin -p < scripts/add_llm_nationality_column.sql)"

echo ""
echo "=================================================="
echo "✓ Deployment Complete!"
echo "=================================================="
echo ""
echo "Next steps:"
echo "  1. Add llm_nationality column to database (see SQL above)"
echo "  2. Run test job: ./scripts/run_nationality_enricher.sh --dry-run"
echo "  3. Check logs: aws logs tail /aws-glue/jobs/output --follow"
echo "  4. Run production: ./scripts/run_nationality_enricher.sh"
echo ""
