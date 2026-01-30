# QuickSight Dashboard Management Scripts

## Overview

This directory contains automation scripts for managing QuickSight dashboards as code, supporting the workflow outlined in the TODO.md.

## Scripts

### 1. `deploy_dashboards.py`

Automates QuickSight dashboard deployment and export.

**Features:**
- Export existing dashboards to JSON templates
- Deploy dashboards from JSON templates
- Support for multiple environments (dev/prod)
- Automatic versioning and publishing

**Installation:**
```bash
pip install boto3
```

**Usage:**

#### Export Existing Dashboards

```bash
# Export a specific dashboard
python deploy_dashboards.py \
  --export \
  --dashboard-id daily-activity-dashboard \
  --output-dir ../../quicksight/dashboards

# Export all dashboards in account
python deploy_dashboards.py \
  --export-all \
  --output-dir ../../quicksight/dashboards
```

#### Deploy Dashboards

```bash
# Deploy all dashboards from templates
python deploy_dashboards.py \
  --environment prod \
  --dashboard-dir ../../quicksight/dashboards

# Deploy specific dashboard
python deploy_dashboards.py \
  --environment prod \
  --dashboard-file ../../quicksight/dashboards/daily-activity.json
```

## Workflow: Automating QuickSight Deployment

### Phase 1: Export Dashboard Definitions (TODO Step 3.1)

**Goal:** Capture existing manually-created dashboards as JSON templates

```bash
# List all dashboards
aws quicksight list-dashboards \
  --aws-account-id $(aws sts get-caller-identity --query Account --output text) \
  --region ap-northeast-1

# Export each dashboard
python deploy_dashboards.py --export-all --output-dir ../../quicksight/dashboards
```

**Output:** JSON files in `quicksight/dashboards/`:
```
quicksight/dashboards/
├── daily-activity-dashboard.json
├── new-contracts-dashboard.json
├── moveouts-dashboard.json
└── moveout-notices-dashboard.json
```

### Phase 2: Store in Version Control (TODO Step 4.1)

```bash
# Templates are already in correct location
cd ../../quicksight/dashboards
git add *.json
git commit -m "docs(quicksight): export dashboard definitions"
git push
```

### Phase 3: Integrate with Terraform (TODO Step 4.2)

The Terraform module at `terraform/modules/quicksight/` provides:
- Data source connection to Aurora
- VPC connection for private subnet access
- IAM roles for QuickSight
- SPICE refresh automation

**Deploy QuickSight infrastructure:**
```bash
cd terraform/environments/prod

# Enable QuickSight module
terraform plan
terraform apply

# Note: Dashboard resources are managed via JSON templates + script
# Not directly in Terraform due to complexity of dashboard definitions
```

### Phase 4: Automate Updates (TODO Step 5.1)

**Workflow for dashboard updates:**

1. **Make changes in QuickSight UI** (easier for visual adjustments)
2. **Export updated definition:**
   ```bash
   python scripts/quicksight/deploy_dashboards.py \
     --export \
     --dashboard-id daily-activity-dashboard \
     --output-dir quicksight/dashboards
   ```
3. **Review changes:**
   ```bash
   git diff quicksight/dashboards/daily-activity-dashboard.json
   ```
4. **Commit to version control:**
   ```bash
   git add quicksight/dashboards/daily-activity-dashboard.json
   git commit -m "feat(quicksight): update daily activity dashboard layout"
   git push
   ```
5. **Deploy to prod:**
   ```bash
   python scripts/quicksight/deploy_dashboards.py \
     --environment prod \
     --dashboard-file quicksight/dashboards/daily-activity-dashboard.json
   ```

## Dashboard Template Structure

JSON templates have this structure:

```json
{
  "dashboard_id": "daily-activity-dashboard",
  "name": "Daily Activity Summary",
  "description": "Overview of daily contract activity",
  "definition": {
    "DataSetIdentifierDeclarations": [...],
    "Sheets": [...],
    "CalculatedFields": [...],
    "ParameterDeclarations": [...],
    "FilterGroups": [...]
  },
  "permissions": [...],
  "tags": {
    "Purpose": "Operations",
    "Dashboard": "DailyActivity"
  }
}
```

## CI/CD Integration

Add to GitHub Actions or similar:

```yaml
# .github/workflows/deploy-quicksight.yml
name: Deploy QuickSight Dashboards

on:
  push:
    branches: [main]
    paths:
      - 'quicksight/dashboards/**'

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Configure AWS Credentials
        uses: aws-actions/configure-aws-credentials@v2
        with:
          role-to-assume: arn:aws:iam::${{ secrets.AWS_ACCOUNT_ID }}:role/github-actions
          aws-region: ap-northeast-1
      
      - name: Deploy Dashboards
        run: |
          pip install boto3
          python scripts/quicksight/deploy_dashboards.py \
            --environment prod \
            --dashboard-dir quicksight/dashboards
```

## SPICE Dataset Refresh

The Terraform module includes automatic SPICE refresh:

```hcl
# terraform/environments/prod/main.tf
module "quicksight" {
  source = "../../modules/quicksight"
  
  enable_spice_refresh    = true
  spice_refresh_schedule  = "cron(0 23 * * ? *)"  # 8 AM JST
  spice_dataset_ids       = "dataset-1,dataset-2,dataset-3"
  
  # ... other variables
}
```

**Manual SPICE refresh:**
```bash
# Refresh specific dataset
aws quicksight create-ingestion \
  --aws-account-id $(aws sts get-caller-identity --query Account --output text) \
  --data-set-id daily-activity-dataset \
  --ingestion-id refresh-$(date +%Y%m%d-%H%M%S)

# Check ingestion status
aws quicksight describe-ingestion \
  --aws-account-id $(aws sts get-caller-identity --query Account --output text) \
  --data-set-id daily-activity-dataset \
  --ingestion-id <ingestion-id>
```

## Troubleshooting

### Export Fails: "AccessDeniedException"

**Solution:** Ensure your AWS user/role has QuickSight admin permissions:
```bash
aws quicksight update-user \
  --aws-account-id $(aws sts get-caller-identity --query Account --output text) \
  --namespace default \
  --user-name <your-username> \
  --role ADMIN
```

### Deploy Fails: "ResourceNotFoundException"

**Likely cause:** Data source or dataset referenced in dashboard doesn't exist

**Solution:** 
1. Deploy Terraform module first (creates data source)
2. Manually create datasets in QuickSight UI
3. Update dashboard JSON template with correct dataset IDs

### Dashboard Shows No Data

**Checklist:**
- [ ] Aurora database populated with analytics tables
- [ ] QuickSight VPC connection working
- [ ] Security group allows QuickSight → Aurora (port 3306)
- [ ] Dataset preview shows data in QuickSight
- [ ] SPICE refresh completed successfully

## Best Practices

1. **Always export before manual changes** - Capture state before modifications
2. **Test in dev first** - Use `--environment dev` before prod deployment
3. **Version control all templates** - Commit JSON files to git
4. **Document dashboard purpose** - Add clear descriptions in templates
5. **Use descriptive IDs** - `daily-activity-dashboard` not `dashboard-1`
6. **Tag dashboards** - Include purpose, owner, update frequency

## Security Considerations

- Dashboard JSON templates may contain sensitive information (database schemas, field names)
- Store templates in private git repositories only
- Limit QuickSight permissions using IAM policies
- Use VPC connections for private Aurora access
- Rotate Aurora credentials periodically (no dashboard updates needed)

## Next Steps

1. Export your existing QuickSight dashboards
2. Store templates in `quicksight/dashboards/`
3. Deploy Terraform QuickSight module
4. Test automated deployment with one dashboard
5. Expand to all dashboards
6. Set up SPICE refresh automation
7. Document dashboard definitions in team wiki

## Support

For issues or questions:
- Check CloudWatch Logs: `/aws/lambda/tokyobeta-prod-spice-refresh`
- Review QuickSight audit logs in CloudTrail
- Test with AWS CLI before using script
- Verify IAM permissions for QuickSight API actions
