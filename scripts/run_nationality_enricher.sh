#!/bin/bash
# Run LLM Nationality Enricher Glue job
# Usage: ./scripts/run_nationality_enricher.sh [--dry-run] [--max-batch=N]

set -e

JOB_NAME="tokyobeta-nationality-enricher"
REGION="ap-northeast-1"

# Default arguments
DRY_RUN="false"
MAX_BATCH_SIZE="1000"

# Parse command line arguments
for arg in "$@"; do
    case $arg in
        --dry-run)
            DRY_RUN="true"
            shift
            ;;
        --max-batch=*)
            MAX_BATCH_SIZE="${arg#*=}"
            shift
            ;;
        *)
            ;;
    esac
done

echo "=================================================="
echo "Running LLM Nationality Enricher"
echo "=================================================="
echo ""
echo "Configuration:"
echo "  Job Name: ${JOB_NAME}"
echo "  Dry Run: ${DRY_RUN}"
echo "  Max Batch: ${MAX_BATCH_SIZE}"
echo ""

# Start Glue job
echo "Starting Glue job..."
JOB_RUN_ID=$(aws glue start-job-run \
    --job-name "${JOB_NAME}" \
    --arguments '{
        "--DRY_RUN":"'"${DRY_RUN}"'",
        "--MAX_BATCH_SIZE":"'"${MAX_BATCH_SIZE}"'"
    }' \
    --region "${REGION}" \
    --query 'JobRunId' \
    --output text)

if [ $? -eq 0 ]; then
    echo "✓ Job started successfully"
    echo "  Job Run ID: ${JOB_RUN_ID}"
else
    echo "✗ Failed to start job"
    exit 1
fi

echo ""
echo "Monitoring job progress..."
echo ""

# Poll job status
while true; do
    JOB_STATUS=$(aws glue get-job-run \
        --job-name "${JOB_NAME}" \
        --run-id "${JOB_RUN_ID}" \
        --region "${REGION}" \
        --query 'JobRun.JobRunState' \
        --output text)
    
    TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[${TIMESTAMP}] Status: ${JOB_STATUS}"
    
    case "${JOB_STATUS}" in
        SUCCEEDED)
            echo ""
            echo "=================================================="
            echo "✓ Job completed successfully!"
            echo "=================================================="
            echo ""
            echo "Job Run ID: ${JOB_RUN_ID}"
            
            # Get execution time
            EXEC_TIME=$(aws glue get-job-run \
                --job-name "${JOB_NAME}" \
                --run-id "${JOB_RUN_ID}" \
                --region "${REGION}" \
                --query 'JobRun.ExecutionTime' \
                --output text)
            
            echo "Execution Time: ${EXEC_TIME} seconds"
            echo ""
            echo "View logs:"
            echo "  aws logs tail /aws-glue/jobs/output --follow --log-stream-name-prefix ${JOB_RUN_ID}"
            echo ""
            echo "Verify results:"
            echo "  SELECT COUNT(*) FROM staging.tenants WHERE llm_nationality IS NOT NULL;"
            echo ""
            exit 0
            ;;
        FAILED|STOPPED|ERROR)
            echo ""
            echo "=================================================="
            echo "✗ Job failed!"
            echo "=================================================="
            echo ""
            echo "Check error logs:"
            echo "  aws logs tail /aws-glue/jobs/error --log-stream-name-prefix ${JOB_RUN_ID}"
            echo ""
            
            # Get error message
            ERROR_MSG=$(aws glue get-job-run \
                --job-name "${JOB_NAME}" \
                --run-id "${JOB_RUN_ID}" \
                --region "${REGION}" \
                --query 'JobRun.ErrorMessage' \
                --output text)
            
            if [ ! -z "${ERROR_MSG}" ] && [ "${ERROR_MSG}" != "None" ]; then
                echo "Error: ${ERROR_MSG}"
            fi
            
            exit 1
            ;;
        RUNNING|STARTING|STOPPING)
            # Job still in progress, wait and check again
            sleep 10
            ;;
        *)
            echo "Unknown status: ${JOB_STATUS}"
            sleep 10
            ;;
    esac
done
