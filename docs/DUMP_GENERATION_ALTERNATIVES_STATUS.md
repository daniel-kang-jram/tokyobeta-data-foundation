# Dump Generation Alternatives - Status & Roadmap

**Last Updated:** 2026-02-05  
**Current Status:** 📝 **Documented, Not Yet Implemented**

## Executive Summary

We have **documented** two alternative approaches to the current EC2-based SQL dump generation, but **neither has been implemented yet**. The current system (EC2 cron job) remains operational and there's no urgent need to migrate.

## Current Production Setup ✅

### How It Works Now

**Daily at 5:30 AM JST:**
1. EC2 instance (`i-00523f387117d497b`) runs cron job
2. `ggh_datatransit.sh` executes `mysqldump` against Nazca's RDS
3. Dump compressed and uploaded to `s3://jram-gghouse/dumps/`
4. File size: ~945MB (compressed)
5. Our Glue ETL downloads at 7:00 AM JST

**Status:** ✅ **Working reliably**

### Issues with Current Approach

| Issue | Severity | Impact |
|-------|----------|--------|
| Hardcoded credentials in scripts | 🔴 High | Security risk, difficult to rotate |
| Static AWS keys in `~/.aws/credentials` | 🔴 High | Credentials can be leaked |
| Dependency on single EC2 instance | 🟡 Medium | Single point of failure |
| Daily batch only (no real-time data) | 🟡 Medium | 24-hour data latency |
| Manual maintenance required | 🟢 Low | Infrequent, manageable |

## Alternative 1: AWS DMS (Database Migration Service)

### Status: 📝 **Documented, Not Started**

**Documentation:**
- `docs/DMS_VENDOR_REQUIREMENTS.md` - Technical requirements
- `docs/NAZCA_EMAIL_DRAFT.md` - Vendor communication template

### What It Would Provide

**Benefits:**
- ✅ **Real-time data** via Change Data Capture (CDC)
- ✅ **No EC2 dependency** - fully managed service
- ✅ **Automatic failover** - built-in high availability
- ✅ **Incremental updates** - not full dumps
- ✅ **Reduced latency** - seconds vs 24 hours

**Requirements from Nazca (Vendor):**

1. **Network Connectivity**
   - VPC Peering OR Transit Gateway OR VPN
   - Security group rules (port 3306)
   
2. **Database User**
   ```sql
   CREATE USER 'dms_replication_user'@'%' IDENTIFIED BY '<password>';
   GRANT REPLICATION CLIENT ON *.* TO 'dms_replication_user'@'%';
   GRANT REPLICATION SLAVE ON *.* TO 'dms_replication_user'@'%';
   GRANT SELECT ON basis.* TO 'dms_replication_user'@'%';
   ```

3. **RDS Configuration**
   - `binlog_format = ROW`
   - `binlog_row_image = FULL`
   - Backup retention > 0 (for binlog)

4. **Timeline**
   - **Estimated:** 1-2 weeks from kickoff
   - **Effort:** Moderate (requires vendor coordination)

### Why Not Implemented Yet

- ❌ **Not contacted Nazca** - Email draft ready but not sent
- ❌ **Requires vendor cooperation** - Network setup, credentials, config
- ❌ **Current system working fine** - No urgent need
- ⏳ **Deferred to Phase 2** - Focus on core ETL first

### Implementation Roadmap (If/When Needed)

**Phase 1: Vendor Coordination (Week 1-2)**
- [ ] Send email to Nazca (use draft in `docs/NAZCA_EMAIL_DRAFT.md`)
- [ ] Exchange VPC details
- [ ] Establish VPC peering connection

**Phase 2: Database Setup (Week 3)**
- [ ] Nazca creates replication user
- [ ] Verify binlog settings (may need RDS reboot)
- [ ] Configure security groups

**Phase 3: DMS Implementation (Week 4)**
- [ ] Create DMS replication instance
- [ ] Configure source endpoint (Nazca RDS)
- [ ] Configure target endpoint (Our Aurora)
- [ ] Create migration task (full load + CDC)

**Phase 4: Testing & Cutover (Week 5-6)**
- [ ] Run DMS in parallel with dumps
- [ ] Validate data consistency
- [ ] Update Glue ETL to use DMS-replicated data
- [ ] Decommission EC2 cron job

**Estimated Cost:**
- DMS Replication Instance: ~$50-100/month
- Data transfer: Minimal (same region, VPC peering)
- **Total:** ~$60-110/month additional

## Alternative 2: Secure EC2 Cron (Security Improvement)

### Status: 📝 **Documented, Not Implemented**

**Documentation:**
- `docs/SECURITY_MIGRATION_PLAN.md` - Complete migration plan
- `scripts/example_cron_scripts/` - Example scripts with Secrets Manager

### What It Would Provide

**Security Improvements:**
- ✅ **No hardcoded credentials** - Use AWS Secrets Manager
- ✅ **IAM instance role** - No static AWS keys
- ✅ **Centralized rotation** - Update secrets once
- ✅ **Audit trail** - CloudTrail logs all access
- ✅ **Least privilege** - Role has only required permissions

**What Stays the Same:**
- Still EC2-based (same dependency)
- Still daily batch dumps (no real-time)
- Still requires EC2 maintenance

### Why Not Implemented Yet

- ❌ **Not urgent** - Current security acceptable for private network
- ❌ **Requires EC2 downtime** - To attach IAM role
- ❌ **Needs careful testing** - 4-phase migration plan
- ⏳ **Lower priority** - No active security incidents

### Implementation Roadmap (If/When Needed)

**Phase 1: Infrastructure Setup** (1 day, no downtime)
- [ ] Deploy Terraform: IAM role, Secrets Manager
- [ ] Store RDS credentials in Secrets Manager
- [ ] Test access from local machine

**Phase 2: Parallel Testing** (1-2 weeks, no downtime)
- [ ] Deploy example scripts to EC2
- [ ] Run new scripts alongside old ones
- [ ] Upload to `s3://jram-gghouse/dumps-test/`
- [ ] Compare outputs daily

**Phase 3: Attach IAM Role** (15 minutes, requires EC2 restart)
- [ ] Schedule maintenance window
- [ ] Stop EC2, attach role, start EC2
- [ ] Verify IAM role works
- [ ] Rollback plan ready

**Phase 4: Gradual Cutover** (2-4 weeks)
- [ ] Week 1: Replace contract status cron
- [ ] Week 2: Replace main dump cron (highest risk)
- [ ] Week 3-4: Replace remaining crons
- [ ] Each validated 2-3 days before next

**Estimated Cost:**
- Secrets Manager: ~$1/month (2 secrets × $0.40 + API calls)
- **Total:** Negligible cost increase

## Recommendation Matrix

| Factor | Continue EC2 | Secure EC2 | AWS DMS |
|--------|--------------|------------|---------|
| **Data Latency** | 24 hours ⚠️ | 24 hours ⚠️ | Real-time ✅ |
| **Security** | Low ⚠️ | High ✅ | High ✅ |
| **Reliability** | Medium ⚠️ | Medium ⚠️ | High ✅ |
| **Cost** | Current | +$1/mo | +$60-110/mo |
| **Vendor Dependency** | Low ✅ | Low ✅ | High ⚠️ |
| **Implementation Time** | N/A | 1 month | 1-2 months |
| **Maintenance** | Manual | Manual | Automatic |
| **Risk of Change** | None | Low | Medium |

## Decision Criteria

### When to Implement Secure EC2

**Triggers:**
- Security audit requires credential management
- Compliance requirement for secret rotation
- Before adding more team members with EC2 access
- If credentials are accidentally exposed

**Blockers:**
- None - can implement anytime

### When to Implement AWS DMS

**Triggers:**
- Business requires real-time data (< 1 hour latency)
- EC2 instance becomes unreliable
- Dashboard user count grows significantly (need fresher data)
- Vendor (Nazca) willing to cooperate

**Blockers:**
- Requires Nazca coordination and approval
- Network connectivity setup with vendor
- RDS configuration changes (may need downtime)
- Higher ongoing costs

## Current Status Summary

### What's Production Today

```
EC2 Instance (i-00523f387117d497b)
  └─ Cron: 5:30 AM JST
     └─ mysqldump → S3 → Glue ETL
        └─ 24-hour latency
        └─ Hardcoded credentials (security risk)
        └─ Works reliably ✅
```

### What's Documented (Not Implemented)

```
Option A: Secure EC2
  - Use Secrets Manager + IAM roles
  - Same latency (24 hours)
  - Better security ✅
  - 1-month migration

Option B: AWS DMS
  - Real-time CDC replication
  - No EC2 dependency
  - Requires Nazca setup
  - 1-2 month implementation
```

## Next Steps (If Pursuing Either Alternative)

### For Secure EC2 Migration

1. **Week 1:** Deploy Terraform (Phase 1)
   ```bash
   cd terraform/environments/prod
   terraform apply  # IAM role + Secrets Manager
   ```

2. **Week 2-3:** Parallel testing (Phase 2)
   - Deploy example scripts
   - Run alongside existing crons
   - Compare outputs

3. **Week 4:** Attach IAM role (Phase 3)
   - Schedule EC2 restart window
   - Attach role during low-usage period

4. **Week 5-8:** Gradual cutover (Phase 4)
   - One cron at a time
   - Validate each for 2-3 days

### For AWS DMS Implementation

1. **Week 1:** Contact Nazca
   - Send email (draft ready in `docs/NAZCA_EMAIL_DRAFT.md`)
   - Schedule technical call
   - Exchange requirements

2. **Week 2-3:** Network setup
   - Establish VPC peering
   - Configure security groups
   - Test connectivity

3. **Week 4-5:** DMS setup
   - Create replication user (Nazca)
   - Deploy DMS replication instance
   - Configure endpoints

4. **Week 6-8:** Testing & cutover
   - Initial full load
   - CDC testing
   - Parallel validation
   - Update Glue ETL

## Questions & Decisions Needed

### Business Questions

1. **Is 24-hour data latency acceptable long-term?**
   - If yes → No rush for DMS
   - If no → Prioritize DMS implementation

2. **How critical is security compliance?**
   - If critical → Implement Secure EC2 soon
   - If acceptable → Defer security improvements

3. **What is budget for data platform improvements?**
   - <$5/month → Keep current setup
   - $5-10/month → Secure EC2 only
   - $60-110/month → Consider DMS

### Technical Questions

4. **Is Nazca willing to support DMS?**
   - Need to contact them (email draft ready)
   - May prefer not to expose production RDS

5. **Can we schedule EC2 downtime for IAM role?**
   - Required for Secure EC2 migration
   - 10-15 minute window needed

6. **What is our risk tolerance for vendor lock-in?**
   - DMS creates dependency on Nazca cooperation
   - If they change systems, DMS breaks

## Related Documentation

- **DMS Requirements:** `docs/DMS_VENDOR_REQUIREMENTS.md`
- **DMS Email Draft:** `docs/NAZCA_EMAIL_DRAFT.md`
- **Security Plan:** `docs/SECURITY_MIGRATION_PLAN.md`
- **Example Scripts:** `scripts/example_cron_scripts/`
- **Current Architecture:** `docs/UPDATED_ARCHITECTURE.md`

## Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-01-31 | Document alternatives | Prepare for future improvements |
| 2026-02-05 | Defer both implementations | Current system working, focus on core ETL |
| TBD | Re-evaluate DMS | If business needs real-time data |
| TBD | Implement Secure EC2 | If security audit requires it |

---

**Recommendation:** Continue with current EC2-based dumps for now. Implement **Secure EC2** if security becomes a priority, or implement **AWS DMS** if business requires real-time data.

**Priority:** Low (current system adequate)  
**Next Review:** 2026-06-01 (4 months)
