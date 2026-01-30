#!/bin/bash
# Helper script to retrieve current RDS credentials from EC2 instance
# This helps you find the credentials needed for rds_cron_secret.tf

set -e

echo "=== Finding RDS Credentials from EC2 Instance ==="
echo ""

# Get EC2 IP address
EC2_IP=$(aws ec2 describe-instances \
  --instance-ids i-00523f387117d497b \
  --profile gghouse \
  --query 'Reservations[0].Instances[0].PublicIpAddress' \
  --output text)

if [ "$EC2_IP" = "None" ] || [ -z "$EC2_IP" ]; then
  echo "❌ EC2 instance does not have a public IP or is not running"
  echo "Instance ID: i-00523f387117d497b"
  exit 1
fi

echo "✅ EC2 Instance IP: $EC2_IP"
echo ""
echo "To retrieve credentials, run these commands:"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "# 1. SSH into EC2 instance"
echo "ssh ubuntu@${EC2_IP}"
echo ""
echo "# 2. Look for DB credentials in cron scripts"
echo "grep -h -E 'DB_HOST=|DB_USER=|DB_PASS=' ~/cron_scripts/*.sh 2>/dev/null | head -10"
echo ""
echo "# OR if variables are set differently:"
echo "grep -h -E 'MYSQL_HOST=|MYSQL_USER=|MYSQL_PWD=' ~/cron_scripts/*.sh 2>/dev/null"
echo ""
echo "# 3. Copy the values you see"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Alternative: Check the actual script files"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "ssh ubuntu@${EC2_IP} 'cat ~/cron_scripts/ggh_datatransit.sh' | grep -E 'DB_HOST|DB_USER|DB_PASS|mysql' | head -20"
echo ""
echo "Once you have the credentials:"
echo "1. Edit: terraform/environments/prod/rds_cron_secret.tf"
echo "2. Replace the placeholder values"
echo "3. Run: terraform plan"
echo ""
