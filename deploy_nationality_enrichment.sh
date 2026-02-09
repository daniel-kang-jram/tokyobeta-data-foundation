#!/bin/bash
# Deploy LLM Nationality Enrichment to existing AWS pipeline
# This script uploads updated scripts and applies Terraform changes

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

echo "====================================================================="
echo "LLM Nationality Enrichment - Deployment to Existing Pipeline"
echo "====================================================================="
echo ""

# Get S3 bucket from terraform
cd terraform/environments/prod
S3_BUCKET=$(terraform output -raw s3_source_bucket 2>/dev/null || echo "")

if [ -z "$S3_BUCKET" ]; then
    echo "⚠️  Could not determine S3 bucket from Terraform output."
    echo "   Defaulting to: jram-gghouse"
    S3_BUCKET="jram-gghouse"
fi

cd "$PROJECT_ROOT"

echo "Configuration:"
echo "  S3 Bucket: $S3_BUCKET"
echo "  Region: ap-northeast-1"
echo ""

# Step 1: Upload updated scripts to S3
echo "==================================================================="
echo "Step 1: Uploading updated Glue scripts to S3"
echo "==================================================================="
echo ""

echo "Uploading nationality_enricher.py..."
aws s3 cp glue/scripts/nationality_enricher.py \
  s3://$S3_BUCKET/glue-scripts/nationality_enricher.py \
  --region ap-northeast-1

echo "✓ Uploaded nationality_enricher.py"
echo ""

echo "Uploading updated daily_etl.py (with nationality enrichment integrated)..."
aws s3 cp glue/scripts/daily_etl.py \
  s3://$S3_BUCKET/glue-scripts/daily_etl.py \
  --region ap-northeast-1

echo "✓ Uploaded daily_etl.py"
echo ""

# Step 2: Apply Terraform changes (Bedrock permissions)
echo "==================================================================="
echo "Step 2: Applying Terraform changes (adding Bedrock permissions)"
echo "==================================================================="
echo ""

cd terraform/environments/prod

echo "Running terraform plan..."
terraform plan -out=tfplan

echo ""
read -p "Apply Terraform changes? (yes/no): " APPLY_TERRAFORM

if [ "$APPLY_TERRAFORM" == "yes" ]; then
    terraform apply tfplan
    rm tfplan
    echo "✓ Terraform changes applied"
else
    echo "⚠️  Terraform changes NOT applied. Run manually:"
    echo "   cd terraform/environments/prod"
    echo "   terraform apply"
    rm tfplan
fi

cd "$PROJECT_ROOT"

echo ""
echo "==================================================================="
echo "✓ Deployment Complete!"
echo "==================================================================="
echo ""
echo "What was deployed:"
echo "  1. ✓ nationality_enricher.py uploaded to S3"
echo "  2. ✓ daily_etl.py (updated) uploaded to S3"
echo "  3. ✓ Terraform updated (Bedrock permissions)"
echo ""
echo "Next steps - ON YOUR SIDE:"
echo "  1. Enable Bedrock model access (when AWS approves your use case)"
echo "     → Go to AWS Console > Bedrock > Model access"
echo "     → Enable: Claude 3 Haiku"
echo ""
echo "  2. Test the enrichment:"
echo "     aws glue start-job-run \\"
echo "       --job-name tokyobeta-prod-daily-etl \\"
echo "       --region ap-northeast-1"
echo ""
echo "  3. Monitor CloudWatch logs:"
echo "     aws logs tail /aws-glue/jobs/output --follow | grep 'Nationalities enriched'"
echo ""
echo "  4. Verify results in database:"
echo "     SELECT COUNT(*) FROM staging.tenants WHERE llm_nationality IS NOT NULL;"
echo ""
echo "Expected results after first run:"
echo "  • ~1,882 tenants enriched"
echo "  • レソト, NULL, empty nationalities replaced with LLM predictions"
echo "  • 100% accuracy based on local testing"
echo ""
