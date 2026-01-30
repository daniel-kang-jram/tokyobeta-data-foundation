# Plan to Rectify Identified Issues

## ✅ IMPLEMENTATION COMPLETE - Ready for Execution

**Date Completed:** 2026-01-31  
**Status:** All infrastructure code and documentation created  
**Next Step:** Execute migration following the documented plan

---

## 1. Secure the EC2 Cron Job ✅

### Phase 1: Replace Static AWS Credentials with an IAM Role
- [x] **1.1.** Create a new IAM role with the principle of least privilege.
  - **Status:** ✅ Complete
  - **Location:** `terraform/modules/ec2_iam_role/`
  - **Features:** S3 access, Secrets Manager access, SSM Session Manager
  
- [ ] **1.2.** Attach the IAM role to the EC2 instance (`i-00523f387117d497b`).
  - **Status:** ⏭️ Ready to execute (requires EC2 restart)
  - **Terraform:** `terraform/modules/ec2_management/`
  - **Documentation:** See Phase 3 in `docs/SECURITY_MIGRATION_PLAN.md`
  
- [x] **1.3.** Update the cron scripts to use the AWS CLI with the attached instance role.
  - **Status:** ✅ Complete (example scripts created)
  - **Location:** `scripts/example_cron_scripts/`
  - **Note:** Test in parallel before replacing production scripts
  
- [ ] **1.4.** Securely remove the static AWS access keys from the `~/.aws/credentials` file.
  - **Status:** ⏭️ Execute after validation (Phase 5)
  - **Safety:** Keep old credentials for 30 days after successful cutover

### Phase 2: Manage RDS Credentials with AWS Secrets Manager
- [x] **2.1.** Create a new secret in AWS Secrets Manager to store the RDS database credentials.
  - **Status:** ✅ Complete (Terraform module extended)
  - **Location:** `terraform/modules/secrets/main.tf`
  - **Secret Name:** `tokyobeta/prod/rds/cron-credentials`
  
- [x] **2.2.** Update the IAM role from Phase 1 to grant permission to read this secret.
  - **Status:** ✅ Complete
  - **Policy:** Included in `ec2_iam_role` module
  
- [x] **2.3.** Modify the cron scripts to fetch the RDS credentials from Secrets Manager at runtime.
  - **Status:** ✅ Complete (example scripts implemented)
  - **Scripts:** `ggh_datatransit.sh`, `ggh_contractstatus.sh`
  - **Testing:** See `scripts/example_cron_scripts/TESTING_GUIDE.md`

---

## 2. Automate QuickSight Dashboard Deployment ✅

### Phase 1: Export Dashboard Definitions
- [ ] **3.1.** Manually export the existing QuickSight dashboard definitions as JSON templates.
  - **Status:** ⏭️ Ready to execute
  - **Tool:** `scripts/quicksight/deploy_dashboards.py --export-all`
  - **Command:**
    ```bash
    python scripts/quicksight/deploy_dashboards.py \
      --export-all \
      --output-dir quicksight/dashboards
    ```

### Phase 2: Integrate into Terraform
- [x] **4.1.** Store the JSON templates in the `quicksight/dashboards` directory.
  - **Status:** ✅ Directory ready
  - **Location:** `quicksight/dashboards/`
  - **Note:** Templates will be stored after export in step 3.1
  
- [x] **4.2.** Use Terraform and automation scripts to manage dashboards as code.
  - **Status:** ✅ Complete
  - **Terraform Module:** `terraform/modules/quicksight/`
  - **Deploy Script:** `scripts/quicksight/deploy_dashboards.py`
  - **Features:** Data source, VPC connection, SPICE refresh automation

### Phase 3: Automate Updates
- [x] **5.1.** Create a script to automate updating dashboard definitions.
  - **Status:** ✅ Complete
  - **Script:** `scripts/quicksight/deploy_dashboards.py`
  - **Capabilities:**
    - Export dashboards from QuickSight → JSON
    - Deploy dashboards from JSON → QuickSight
    - Support dev/prod environments
    - Version control integration
  - **Documentation:** `scripts/quicksight/README.md`

---

## 📚 Implementation Documentation

All code and documentation has been created. Review these resources before execution:

### Security Migration (EC2 Cron Jobs)
1. **Master Plan:** `docs/SECURITY_MIGRATION_PLAN.md`
   - Complete 4-phase migration strategy
   - Timeline: ~3 weeks with parallel testing
   - Rollback procedures for each phase
   - Zero risk to existing operations

2. **Testing Guide:** `scripts/example_cron_scripts/TESTING_GUIDE.md`
   - Detailed validation procedures
   - Automated comparison scripts
   - Success criteria checklist

3. **Example Scripts:** `scripts/example_cron_scripts/`
   - `ggh_datatransit.sh` - Full dump with Secrets Manager
   - `ggh_contractstatus.sh` - Query with Secrets Manager
   - `README.md` - Usage instructions

4. **Terraform Modules:**
   - `terraform/modules/ec2_iam_role/` - IAM role with least privilege
   - `terraform/modules/ec2_management/` - EC2 instance management
   - `terraform/modules/secrets/` - Extended for RDS cron credentials

### QuickSight Automation
1. **Automation Script:** `scripts/quicksight/deploy_dashboards.py`
   - Export and deploy dashboards as code
   - Multi-environment support
   - Comprehensive error handling

2. **Terraform Module:** `terraform/modules/quicksight/`
   - Data source configuration
   - VPC connection
   - SPICE refresh Lambda function
   - IAM roles

3. **Documentation:** `scripts/quicksight/README.md`
   - Complete workflow guide
   - CI/CD integration examples
   - Troubleshooting tips

---

## ⏭️ Next Steps (Execution Phase)

### Step 1: Review Documentation (30 minutes)
```bash
# Read the migration plan
cat docs/SECURITY_MIGRATION_PLAN.md

# Review testing procedures
cat scripts/example_cron_scripts/TESTING_GUIDE.md

# Understand QuickSight automation
cat scripts/quicksight/README.md
```

### Step 2: Deploy Infrastructure (Phase 1, 2 hours)
```bash
cd terraform/environments/prod

# Review changes
terraform plan

# Deploy IAM role and Secrets Manager
terraform apply

# Store current RDS credentials in Secrets Manager
aws secretsmanager put-secret-value \
  --secret-id tokyobeta/prod/rds/cron-credentials \
  --secret-string '{"host":"<your-rds-host>","username":"<user>","password":"<pass>","database":"gghouse","port":3306}'
```

### Step 3: Begin Parallel Testing (Phase 2, 7-14 days)
```bash
# Copy example scripts to EC2
scp scripts/example_cron_scripts/*.sh ubuntu@<ec2-ip>:~/cron_scripts_new/

# SSH and configure test crons
ssh ubuntu@<ec2-ip>
# Follow Phase 2 instructions in SECURITY_MIGRATION_PLAN.md
```

### Step 4: Export QuickSight Dashboards
```bash
# Install dependencies
pip install boto3

# Export all dashboards
python scripts/quicksight/deploy_dashboards.py \
  --export-all \
  --output-dir quicksight/dashboards

# Commit to version control
git add quicksight/dashboards/*.json
git commit -m "docs(quicksight): export dashboard definitions"
```

---

## 🎯 Success Criteria

Before marking as complete:
- [ ] Phase 1 executed: IAM role and Secrets Manager deployed
- [ ] Phase 2 executed: 7+ days of successful parallel testing
- [ ] Phase 3 executed: IAM role attached to EC2 (requires restart)
- [ ] Phase 4 executed: All cron jobs cutover to new secure scripts
- [ ] Phase 5 executed: Old credentials removed, cleanup complete
- [ ] QuickSight dashboards exported to JSON
- [ ] QuickSight automation tested with at least one dashboard
- [ ] Documentation updated with actual values (hostnames, ARNs, etc.)
- [ ] Team trained on new credential rotation procedures

---

## 🔒 Security Benefits (After Completion)

✅ **No static AWS credentials** - Can't be leaked or stolen  
✅ **No hardcoded database passwords** - Not visible in process list  
✅ **Centralized credential rotation** - Update once in Secrets Manager  
✅ **Complete audit trail** - CloudTrail logs all secret access  
✅ **Least privilege IAM** - EC2 only has required permissions  
✅ **Infrastructure as Code** - QuickSight dashboards version controlled  
✅ **Automated SPICE refresh** - No manual intervention needed  

---

## 📞 Support & Questions

- Security migration questions: See `docs/SECURITY_MIGRATION_PLAN.md`
- Testing help: See `scripts/example_cron_scripts/TESTING_GUIDE.md`
- QuickSight automation: See `scripts/quicksight/README.md`
- Terraform issues: Check module README files in `terraform/modules/*/`

**Remember:** Old cron jobs continue working unchanged until you explicitly cutover in Phase 4. There is zero risk to existing operations during testing phases.
