# Email Draft to Nazca (V3 PMS Vendor)

---

**Subject**: Request for AWS DMS Setup - Real-Time Data Replication from basis RDS

**To**: Nazca Technical Support / Account Manager

**CC**: JRAM Technical Team, GGhouse Operations

---

Dear Nazca Team,

We are writing to request technical assistance in setting up **AWS Database Migration Service (DMS)** for real-time data replication from the `basis` RDS instance to our analytics infrastructure.

## Background

Currently, we are using daily SQL dumps from the `basis` RDS database for analytics purposes. To improve data freshness and reduce operational overhead, we would like to implement Change Data Capture (CDC) using AWS DMS. This will allow us to receive near real-time updates instead of once-daily batch dumps.

## What We Need from Nazca

### 1. Network Connectivity (VPC Peering)

We need to establish private network connectivity between our AWS VPC and yours.

**Our VPC Details**:
- **VPC ID**: `vpc-0973d4c359b12f522`
- **AWS Account**: 343881458651
- **CIDR Block**: 10.0.0.0/16
- **Region**: ap-northeast-1

**Please provide**:
- Your VPC ID (where `basis` RDS resides)
- Your VPC CIDR block
- Confirmation to initiate VPC Peering connection

We can initiate the peering request from our side once you provide the VPC ID.

### 2. Database User with Replication Privileges

Please create a dedicated MySQL user for DMS replication with the following privileges:

```sql
CREATE USER 'dms_replication_gghouse'@'%' IDENTIFIED BY '<secure-password>';

GRANT REPLICATION CLIENT ON *.* TO 'dms_replication_gghouse'@'%';
GRANT REPLICATION SLAVE ON *.* TO 'dms_replication_gghouse'@'%';
GRANT SELECT ON basis.* TO 'dms_replication_gghouse'@'%';

FLUSH PRIVILEGES;
```

**Please provide**:
- Username created (e.g., `dms_replication_gghouse`)
- Password (via secure channel - Secrets Manager or encrypted email)

### 3. RDS Configuration Verification

DMS requires specific MySQL binlog settings. Please confirm the following:

```sql
-- Please run these queries and share the output:
SHOW VARIABLES LIKE 'binlog_format';       -- Must be 'ROW'
SHOW VARIABLES LIKE 'binlog_row_image';    -- Must be 'FULL'  
SHOW VARIABLES LIKE 'binlog_retention_hours';  -- Should be > 0
```

**If these are not set correctly**, please:
- Update the RDS parameter group to enable:
  - `binlog_format = ROW`
  - `binlog_row_image = FULL`
- **Note**: This may require an RDS instance reboot. Please coordinate a maintenance window with us.

### 4. Security Group Access

Once VPC peering is established, please add an inbound rule to the `basis` RDS security group:

**Inbound Rule**:
- **Type**: MySQL/Aurora (3306)
- **Protocol**: TCP
- **Port**: 3306
- **Source**: 10.0.10.0/24 (our DMS subnet)
- **Description**: DMS replication from GGhouse analytics account

We will provide the exact DMS replication instance IP addresses once the instance is created.

### 5. RDS Instance Information

Please confirm the following details:

- **RDS Endpoint**: `basis-instance-1.cr46qo6y4bbb.ap-northeast-1.rds.amazonaws.com` (correct?)
- **Database Name**: `basis`
- **Engine**: aurora-mysql or mysql
- **Engine Version**: (e.g., 8.0.35)
- **Multi-AZ**: Yes/No
- **Read Replicas**: Do you have read replicas we could use instead? (less impact on production)

## Tables We Need to Replicate

We need real-time replication of the following tables from the `basis` database:

**Core tables** (must-have):
- `movings`
- `tenants`
- `apartments`
- `rooms`

**Supporting tables** (preferred):
- All master tables (`m_*`)
- Financial tables (`payments`, `clearings`, `deposits`, etc.)

**Request**: Can we replicate the entire `basis` database, or should we specify individual tables?

## Alternative: Read Replica Access (If DMS is Complex)

If setting up DMS replication is too complex or impactful, an alternative approach would be:

**Option**: Provide us with access to an RDS **read replica**
- We can set up DMS from your read replica → our Aurora
- Zero impact on your production RDS
- You maintain full control of the source data

## Timeline & Next Steps

We are flexible on timeline and happy to work around your maintenance windows.

**Proposed timeline**:
1. **Week 1**: Exchange VPC details, create VPC peering
2. **Week 2**: Create replication user, verify binlog settings
3. **Week 3**: Configure security groups, test connectivity
4. **Week 4**: DMS setup and initial full load
5. **Week 5**: CDC testing and validation

**Questions for you**:
1. Do you have any concerns about enabling DMS replication from our account?
2. What is your preferred method: VPC Peering, Transit Gateway, or VPN?
3. Can you provide a read replica endpoint instead of production RDS?
4. What maintenance windows are available for RDS parameter changes (if needed)?
5. Are there any compliance or security policies we should be aware of?

## Our Commitment

- We will only **read** data via DMS (no writes to your RDS)
- Our DMS will be isolated in a private subnet with strict security groups
- We will monitor DMS latency to ensure minimal impact on your RDS
- We can pause/stop DMS replication at any time if issues arise

## Contact Information

For technical coordination:
- **Primary Contact**: [Your Name/Email]
- **AWS Account ID**: 343881458651
- **Project**: Tokyo Beta Real Estate Analytics Dashboard

Please let us know if you need any additional information or have questions about this setup.

Thank you for your support!

Best regards,  
[Your Name]  
[Your Title]  
GGhouse / JRAM

---

**Attachments**:
- `DMS_VENDOR_REQUIREMENTS.md` (detailed technical requirements)
