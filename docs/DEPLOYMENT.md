# Deployment & Security

**Last Updated:** March 1, 2026

This document covers deployment procedures, verification checklists, and the security migration roadmap.

---

## 📚 Table of Contents
1. [Deployment Verification](#deployment-verification)
2. [Evidence Authenticated Release Sign-off](#evidence-authenticated-release-sign-off)
3. [Evidence Rollback Criteria](#evidence-rollback-criteria)
4. [Security Migration Plan](#security-migration-plan)

---

## Deployment Verification

### Pre-flight Checklist

- [ ] **S3 Sync**: All scripts uploaded to `s3://jram-gghouse/glue-scripts/`
- [ ] **dbt Models**: All models uploaded to `s3://jram-gghouse/dbt-project/`
- [ ] **Glue Params**: Job parameters configured correctly
- [ ] **IAM**: Permissions include Bedrock (if using enrichment)
- [ ] **Tests**: Integration tests pass (`python3 test_etl_integration.py`)
- [ ] **Timeouts**: Set to 60 minutes for all jobs

### Verification Steps

#### 1. Check S3 Files
```bash
aws s3 ls s3://jram-gghouse/glue-scripts/ --profile gghouse
# Verify timestamps match your local edits
```

#### 2. Run Integration Tests
```bash
python3 test_etl_integration.py
```
**Expected Output:**
- ✅ Staging loader script exists
- ✅ Enrichment function defined
- ✅ Silver/Gold dependencies check out
- ✅ ALL INTEGRATION TESTS PASSED

#### 3. Execute Pipeline
```bash
# Option A: Run staging loader only
aws glue start-job-run --job-name tokyobeta-prod-staging-loader --profile gghouse

# Option B: Run full pipeline via Step Functions
aws stepfunctions start-execution \
  --state-machine-arn arn:aws:states:ap-northeast-1:343881458651:stateMachine:tokyobeta-prod-etl-orchestrator \
  --profile gghouse
```

#### 4. Monitor Execution
```bash
# Check status
aws glue get-job-run \
  --job-name tokyobeta-prod-staging-loader \
  --run-id <job-run-id> \
  --profile gghouse

# View logs
aws logs tail /aws-glue/jobs/output --log-stream-names <job-run-id> --follow
```

#### 5. Verify Data
```sql
-- Check if data updated
SELECT MAX(updated_at) FROM gold.daily_activity_summary;

-- Check enrichment results
SELECT COUNT(*) FROM staging.tenants WHERE llm_nationality IS NOT NULL;
```

---

## Evidence Authenticated Release Sign-off

Use this section for production release decisions on `https://intelligence.jram.jp`.

### Required smoke execution

```bash
cd /Users/danielkang/tokyobeta-data-consolidation
RUN_ARTIFACT_DIR="artifacts/evidence-auth-smoke/prod-$(date +%Y%m%d-%H%M%S)"

npm --yes --package=playwright exec -- \
  node scripts/evidence/evidence_auth_smoke.mjs \
  --base-url https://intelligence.jram.jp \
  --username "$EVIDENCE_AUTH_USERNAME" \
  --password "$EVIDENCE_AUTH_PASSWORD" \
  --artifact-dir "$RUN_ARTIFACT_DIR"

npm --yes --package=playwright exec -- \
  node scripts/evidence/evidence_auth_smoke.mjs \
  --dry-run \
  --base-url https://intelligence.jram.jp \
  --artifact-dir "$RUN_ARTIFACT_DIR/dryrun" \
  --print-route-matrix > "$RUN_ARTIFACT_DIR/route-matrix.json"
```

Release evidence workflow reference: `.github/workflows/evidence-auth-smoke.yml` (`evidence-auth-smoke`).

### Deterministic GO/NO-GO matrix

GO only if ALL checks pass:
1. Route matrix H1 + KPI markers + time-context markers pass for `/occupancy`, `/moveins`, `/moveouts`, `/geography`, and `/pricing`.
2. `/pricing` includes all required funnel markers:
   - `Overall Conversion Rate (%)`
   - `Municipality Segment Parity (Applications vs Move-ins)`
   - `Nationality Segment Parity (Applications vs Move-ins)`
   - `Monthly Conversion Trend`
3. `KPI Landing (Gold)` is absent on all non-home routes.
4. Metadata requests are valid JSON responses: `content-type` includes `application/json` and no malformed `/api//` request path appears.
5. Console/network logs contain no `Unexpected token '<'` metadata parse errors.
6. Artifact set is complete: per-route screenshots, `console_logs.json`, `network_logs.json`, and `summary.json`.

NO-GO if ANY blocker is present:
1. Any route marker mismatch (H1, KPI marker, time-context marker, or pricing funnel marker).
2. Home fallback marker `KPI Landing (Gold)` appears on a non-home route.
3. Any metadata response is non-JSON, any malformed `/api//` request appears, or JSON parsing fails.
4. Any `Unexpected token '<'` metadata parse error appears in console/network logs.
5. Required artifacts are missing or incomplete.

### Release sign-off template

```markdown
## Evidence Auth Smoke Sign-off

- Date (UTC): YYYY-MM-DD
- Base URL: https://intelligence.jram.jp
- Artifact Directory: artifacts/evidence-auth-smoke/prod-YYYYMMDD-HHMMSS
- Route Matrix Result: PASS | FAIL
- Pricing Funnel Result: PASS | FAIL
- Metadata JSON Result (`application/json` + no `/api//`): PASS | FAIL
- Parse Error Check (`Unexpected token '<'`): PASS | FAIL
- Decision: GO | NO-GO
- Failing Criteria (required when NO-GO): <list each blocker explicitly>
- Approver: <name>
```

Sign-off entries are appended to this file for auditability.

---

## Evidence Rollback Criteria

Run rollback when any NO-GO blocker is detected from the matrix above.

### Rollback triggers
- route marker mismatch on any release-gated route
- missing pricing funnel marker
- Home fallback marker on non-home route
- metadata response not `application/json`
- malformed `/api//` request path
- `Unexpected token '<'` parse errors
- missing artifact evidence

### Rollback sequence
1. Record `NO-GO` sign-off entry in this document with explicit failing criteria and artifact path.
2. Re-run the last-known-good Evidence pipeline execution to restore known-good assets.
3. Re-run authenticated smoke and confirm all deterministic GO checks pass before issuing GO.

Pipeline execution template:
```bash
aws codepipeline start-pipeline-execution \
  --name "<last-known-good-evidence-refresh-pipeline>" \
  --profile gghouse
```

---

## Security Migration Plan

**Status:** Infrastructure Ready, Awaiting Execution  
**Objective:** Migrate EC2 cron job from static credentials to IAM roles + Secrets Manager.

### Current State (Insecure)
- **Static AWS credentials** in `~/.aws/credentials`
- **Hardcoded RDS password** in scripts
- **No audit trail**

### Target State (Secure)
- ✅ **IAM instance role** (no static keys)
- ✅ **Secrets Manager** (encrypted RDS creds)
- ✅ **CloudTrail** audit logs

### Migration Phases

#### Phase 1: Infrastructure Deployment (Ready)
- Deploy Terraform modules: `ec2_iam_role`, `secrets`
- Store RDS credentials in Secrets Manager

#### Phase 2: Parallel Testing (1-2 Weeks)
- Deploy example scripts to `~/cron_scripts_new/`
- Run alongside existing crons (offset by 10 mins)
- Validate output consistency

#### Phase 3: IAM Role Attachment (Maintenance Window)
- Stop EC2 instance
- Attach `tokyobeta-prod-ec2-cron-profile`
- Start EC2 instance
- Verify `aws sts get-caller-identity` works without config

#### Phase 4: Gradual Cutover
- Replace one cron job at a time
- Monitor for 48 hours before next replacement

#### Phase 5: Cleanup
- Remove old scripts and static credentials

### Rollback Plan
- **Phase 1-2:** Stop new scripts, no impact.
- **Phase 3:** Detach IAM profile, instance falls back to `~/.aws/credentials`.
- **Phase 4:** Re-enable old cron lines in crontab.

### Cost Impact
- **New Cost:** ~$0.50/month (Secrets Manager)
- **Benefit:** High security improvement, compliance ready.
