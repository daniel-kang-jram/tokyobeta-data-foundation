#!/bin/bash
#
# Rollback Aurora DB Using Point-in-Time Recovery (PITR)
# Usage: ./rollback_etl.sh [timestamp]
#
# Uses Aurora's automated backups (no extra cost) to restore to a specific time.
# If no timestamp provided, shows available restore windows.
#
# Examples:
#   ./rollback_etl.sh                    # Show available restore times
#   ./rollback_etl.sh "2026-02-04T10:00:00Z"  # Restore to specific time

set -e

PROFILE="${AWS_PROFILE:-gghouse}"
REGION="${AWS_REGION:-ap-northeast-1}"
CLUSTER_ID="tokyobeta-prod-aurora-cluster-public"

echo "=== Aurora PITR Rollback Tool ==="
echo "Cluster: $CLUSTER_ID"
echo "Region: $REGION"
echo "Cost: FREE (uses automated backups)"
echo ""

# Get cluster info and available restore window
CLUSTER_INFO=$(aws rds describe-db-clusters \
    --db-cluster-identifier "$CLUSTER_ID" \
    --profile "$PROFILE" \
    --region "$REGION" \
    --query 'DBClusters[0].{EarliestRestorableTime:EarliestRestorableTime,LatestRestorableTime:LatestRestorableTime,BackupRetention:BackupRetentionPeriod}' \
    --output json)

EARLIEST=$(echo "$CLUSTER_INFO" | jq -r '.EarliestRestorableTime')
LATEST=$(echo "$CLUSTER_INFO" | jq -r '.LatestRestorableTime')
RETENTION=$(echo "$CLUSTER_INFO" | jq -r '.BackupRetention')

echo "Automated Backup Configuration:"
echo "  Retention Period: $RETENTION days"
echo "  Earliest Restore Time: $EARLIEST"
echo "  Latest Restore Time: $LATEST"
echo ""

# If no argument, list recent automated snapshots and ETL times
if [ -z "$1" ]; then
    echo "Recent automated snapshots:"
    aws rds describe-db-cluster-snapshots \
        --db-cluster-identifier "$CLUSTER_ID" \
        --snapshot-type automated \
        --profile "$PROFILE" \
        --region "$REGION" \
        --query "DBClusterSnapshots[0:5].{Time:SnapshotCreateTime,Type:SnapshotType,Status:Status}" \
        --output table
    
    echo ""
    echo "Usage: $0 <timestamp>"
    echo "Example: $0 \"2026-02-04T10:00:00Z\""
    echo ""
    echo "Tip: To restore to 1 hour ago:"
    echo "  $0 \"\$(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ)\""
    exit 0
fi

RESTORE_TIME="$1"

echo "Restore Configuration:"
echo "  Target Time: $RESTORE_TIME"
echo "  New Cluster ID: ${CLUSTER_ID}-pitr-$(date +%Y%m%d-%H%M%S)"
echo ""
echo "WARNING: This will:"
echo "  1. Create NEW cluster from PITR"
echo "  2. Takes 5-10 minutes"
echo "  3. You'll need to update Glue/Terraform to use new endpoint"
echo "  4. Original cluster remains intact (delete manually after verification)"
echo ""
read -p "Continue? Type 'yes': " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "Rollback cancelled"
    exit 1
fi

NEW_CLUSTER_ID="${CLUSTER_ID}-pitr-$(date +%Y%m%d-%H%M%S)"

echo ""
echo "Step 1: Creating new cluster from PITR..."
aws rds restore-db-cluster-to-point-in-time \
    --db-cluster-identifier "$NEW_CLUSTER_ID" \
    --source-db-cluster-identifier "$CLUSTER_ID" \
    --restore-to-time "$RESTORE_TIME" \
    --profile "$PROFILE" \
    --region "$REGION"

echo ""
echo "✅ PITR restore initiated!"
echo ""
echo "New Cluster ID: $NEW_CLUSTER_ID"
echo ""
echo "Next steps:"
echo "  1. Wait 5-10 minutes for restore"
echo "  2. Check status: aws rds describe-db-clusters --db-cluster-identifier $NEW_CLUSTER_ID --profile $PROFILE"
echo "  3. Create instance: aws rds create-db-cluster-instance --db-cluster-identifier $NEW_CLUSTER_ID --db-instance-identifier ${NEW_CLUSTER_ID}-instance-1 --db-instance-class db.t4g.medium --engine aurora-mysql --profile $PROFILE"
echo "  4. Get new endpoint: aws rds describe-db-clusters --db-cluster-identifier $NEW_CLUSTER_ID --query 'DBClusters[0].Endpoint' --profile $PROFILE"
echo "  5. Update Terraform/Glue configuration with new endpoint"
echo "  6. Test data integrity"
echo "  7. Delete old cluster after verification"
echo ""
echo "Cost: $0 (uses existing automated backups)"
