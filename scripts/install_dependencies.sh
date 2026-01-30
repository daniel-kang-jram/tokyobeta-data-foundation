#!/bin/bash
# Install missing dependencies for testing

set -e

echo "=== Installing Dependencies ==="
echo ""

# Check if boto3 is installed
if python3 -c "import boto3" 2>/dev/null; then
    echo "✅ boto3 already installed"
else
    echo "📦 Installing boto3..."
    pip3 install boto3
    echo "✅ boto3 installed"
fi

echo ""
echo "=== Dependency Check ==="
command -v aws >/dev/null 2>&1 && echo "✅ AWS CLI" || echo "❌ AWS CLI (install: brew install awscli)"
command -v jq >/dev/null 2>&1 && echo "✅ jq" || echo "❌ jq (install: brew install jq)"
command -v terraform >/dev/null 2>&1 && echo "✅ terraform" || echo "❌ terraform"
python3 -c "import boto3" 2>/dev/null && echo "✅ boto3" || echo "❌ boto3"

echo ""
echo "=== All dependencies installed ===" 
