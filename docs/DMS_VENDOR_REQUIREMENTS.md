# DMS Setup Requirements from Nazca (RDS Vendor)

## What We Need from Nazca

### 1. Network Connectivity ⭐ CRITICAL

**Option A: VPC Peering (Recommended)**
- VPC Peering connection between:
  - **Our VPC**: `vpc-0973d4c359b12f522` (AWS Account: 343881458651)
  - **Their VPC**: [Nazca to provide VPC ID]
- Route table updates on both sides
- Security group rules allowing traffic

**Option B: Transit Gateway**
- If Nazca already has TGW infrastructure
- Share TGW attachment

**Option C: VPN Connection**
- Site-to-Site VPN between VPCs
- More complex, higher latency

### 2. Database User with Replication Privileges

**Required MySQL/Aurora Privileges**:
```sql
-- Nazca needs to create this user for us
CREATE USER 'dms_replication_user'@'%' IDENTIFIED BY '<strong-password>';

GRANT REPLICATION CLIENT ON *.* TO 'dms_replication_user'@'%';
GRANT REPLICATION SLAVE ON *.* TO 'dms_replication_user'@'%';
GRANT SELECT ON basis.* TO 'dms_replication_user'@'%';

FLUSH PRIVILEGES;
```

**User Details Nazca Should Provide**:
- Username: (e.g., `dms_replication_user`)
- Password: (strong, 32+ characters)
- Host whitelist: Our DMS replication instance IP ranges

### 3. RDS Configuration Requirements

**Binlog Settings** (Nazca must verify/enable):
```sql
-- Check current settings
SHOW VARIABLES LIKE 'binlog_format';
SHOW VARIABLES LIKE 'binlog_row_image';

-- Required values:
binlog_format = 'ROW'           -- Must be ROW, not STATEMENT
binlog_row_image = 'FULL'       -- Captures full row data
```

**Parameter Group**:
- Nazca needs to ensure these are set in RDS parameter group
- May require RDS instance reboot (plan maintenance window)

**Backup Retention**:
- Must be > 0 (binlog retention for CDC)
- Recommended: 7 days minimum

### 4. Security Group Access

**Nazca needs to whitelist our DMS Replication Instance**:
- Our DMS will be in: `subnet-0d63fbf4d0e1f6d20` (10.0.10.0/24)
- Expected IP range: `10.0.10.0/24` (we'll provide exact IPs after DMS creation)
- Port: **3306** (MySQL)

**Nazca's Security Group Rule**:
```
Type: MySQL/Aurora (3306)
Protocol: TCP
Port: 3306
Source: 10.0.10.0/24 (or specific DMS IPs we provide)
Description: DMS replication from GGhouse account
```

### 5. RDS Information Needed from Nazca

Please provide:
- [ ] RDS Endpoint: `basis-instance-1.cr46qo6y4bbb.ap-northeast-1.rds.amazonaws.com` (confirm)
- [ ] Database Name: `basis` (confirm)
- [ ] Engine Version: (e.g., aurora-mysql 8.0.x or mysql 8.0.x)
- [ ] VPC ID: (for VPC peering)
- [ ] CIDR Block: (e.g., 172.31.0.0/16)
- [ ] Availability Zones: (e.g., ap-northeast-1a, 1c)
- [ ] Current binlog_format setting
- [ ] Backup retention period

### 6. Tables to Replicate

**We need replication for these core tables** (from `basis` database):
- `movings` (primary contract data)
- `tenants` (tenant information)
- `apartments` (property master)
- `rooms` (room data)
- `m_nationalities` (master data)
- Plus all other tables in the `basis` database

**Alternatively**: Replicate entire `basis` database

### 7. Maintenance Window Coordination

If Nazca needs to:
- Enable binlog settings (requires reboot)
- Create VPC peering
- Create replication user

**Ask for**:
- Proposed maintenance window
- Expected downtime (if any)
- Rollback plan

## Timeline

| Step | Owner | Duration | Dependencies |
|------|-------|----------|--------------|
| VPC Peering setup | Both | 1-2 days | VPC IDs exchanged |
| Create replication user | Nazca | 30 min | None |
| Enable binlog (if needed) | Nazca | 1-2 hours | Maintenance window |
| Security group rules | Nazca | 30 min | VPC peering complete |
| DMS setup on our side | Us | 1 day | All above complete |
| Initial data load | Automated | 2-4 hours | DMS configured |
| CDC testing | Both | 2-3 days | Initial load complete |

**Total**: 1-2 weeks from kickoff to production CDC

## Alternative: Read Replica Approach

If Nazca is reluctant to set up DMS:

**Option**: They provide us a **read replica** endpoint
- Less intrusive than DMS for them
- We can set up DMS from their read replica → our Aurora
- No impact on their production RDS

Request:
- [ ] Create read replica in their account
- [ ] Share read replica endpoint with us
- [ ] Grant network access via VPC peering
