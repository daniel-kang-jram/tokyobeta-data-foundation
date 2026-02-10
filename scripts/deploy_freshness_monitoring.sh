#!/bin/bash
# Deploy Data Freshness Monitoring Infrastructure
# Creates CloudWatch alarms and Lambda freshness checker

set -e

echo "🚀 Deploying Data Freshness Monitoring"
echo "======================================="

# Ensure correct AWS profile
export AWS_PROFILE=gghouse
export AWS_REGION=ap-northeast-1

echo "✓ AWS Profile: $AWS_PROFILE"
echo "✓ AWS Region: $AWS_REGION"

# Verify we're in correct account
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
if [ "$ACCOUNT" != "343881458651" ]; then
    echo "❌ ERROR: Wrong AWS account ($ACCOUNT)"
    echo "   Expected: 343881458651 (gghouse)"
    echo "   Run: aws sso login --profile gghouse"
    exit 1
fi

echo "✓ AWS Account: $ACCOUNT (gghouse)"
echo ""

# Navigate to Terraform
cd terraform/environments/prod

echo "📋 Planning Terraform changes..."
terraform plan -target=module.monitoring -out=monitoring.tfplan

echo ""
read -p "Review plan above. Apply changes? (y/N): " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo "🚀 Applying Terraform changes..."
    terraform apply monitoring.tfplan
    
    echo ""
    echo "✅ Data Freshness Monitoring Deployed!"
    echo ""
    echo "Next steps:"
    echo "1. Check SNS subscription email (jram-ggh@outlook.com)"
    echo "2. Test Lambda function: aws lambda invoke --function-name tokyobeta-prod-table-freshness-checker --profile gghouse /tmp/output.json"
    echo "3. Check CloudWatch alarms: aws cloudwatch describe-alarms --alarm-name-prefix tokyobeta-prod --profile gghouse"
    echo "4. Verify metrics: CloudWatch Console → Metrics → TokyoBeta/DataQuality"
else
    echo "❌ Deployment cancelled"
    rm -f monitoring.tfplan
    exit 0
fi
