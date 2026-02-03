# QuickSight Setup Guide for Tokyo Beta BI

**Status**: QuickSight not yet enabled  
**AWS Account**: 343881458651  
**Region**: ap-northeast-1

## Prerequisites ✅

- [x] Aurora MySQL cluster running with analytics tables
- [x] ETL job successfully loading data daily
- [x] 4 analytics tables created (2,965 - 17,573 rows each)
- [ ] QuickSight subscription activated

## Step 1: Enable QuickSight (Required - One-Time Setup)

### A. Sign Up for QuickSight

1. **Go to QuickSight console**:
   ```
   https://quicksight.aws.amazon.com/
   ```

2. **Click "Sign up for QuickSight"**

3. **Choose Edition**:
   - Select **"Enterprise"** edition (required for features like row-level security, email reports)
   - Cost: ~$18/user/month + $0.30/GB SPICE capacity

4. **Authentication Method**:
   - Choose **"Use IAM federated identities & QuickSight-managed users"**

5. **QuickSight Account Name**:
   - Account name: `tokyobeta` or `gghouse`
   - Notification email: [your-email@company.com]

6. **QuickSight Permissions**:
   - ✅ Enable auto-discovery of AWS resources
   - ✅ Amazon S3: Select `jram-gghouse` bucket
   - ✅ Amazon Athena (optional, for future use)
   - ✅ AWS Secrets Manager (to read Aurora credentials)

7. **VPC Connection** (Critical for Aurora):
   - ✅ Enable access to **"Amazon VPC resources"**
   - Security Group: Select `tokyobeta-prod-aurora-sg`
   - Subnets: Select private subnets in `tokyobeta-prod-vpc`
   - IAM Role: Let QuickSight create it automatically

8. **Complete Setup**:
   - Click "Finish"
   - Wait 2-3 minutes for account provisioning

### B. Verify QuickSight is Active

```bash
AWS_PROFILE=gghouse aws quicksight describe-account-subscription \
    --aws-account-id 343881458651 \
    --region ap-northeast-1
```

Expected output:
```json
{
    "AccountInfo": {
        "Edition": "ENTERPRISE",
        "AccountSubscriptionStatus": "ACCOUNT_CREATED"
    }
}
```

---

## Step 2: Create VPC Connection for Aurora Access

QuickSight needs a VPC connection to access Aurora MySQL in the private subnet.

### Option A: Via AWS Console (Recommended for First Time)

1. Go to QuickSight → **Manage QuickSight** (top-right)
2. Click **VPC connections** (left menu)
3. Click **Add VPC connection**
4. Configure:
   - **VPC connection name**: `tokyobeta-aurora-connection`
   - **VPC ID**: `tokyobeta-prod-vpc` (from Terraform output)
   - **Subnet ID**: Select a **private subnet** (where Aurora is)
   - **Security group**: `tokyobeta-prod-aurora-sg`
   - **DNS resolver endpoints**: Leave empty (use VPC DNS)
5. Click **Create**

### Option B: Via AWS CLI

```bash
# First, get VPC and subnet IDs from Terraform
cd /Users/danielkang/tokyobeta-data-consolidation/terraform/environments/prod
AWS_PROFILE=gghouse terraform output

# Then create VPC connection
AWS_PROFILE=gghouse aws quicksight create-vpc-connection \
    --aws-account-id 343881458651 \
    --vpc-connection-id tokyobeta-aurora-connection \
    --name "Tokyo Beta Aurora Connection" \
    --subnet-ids subnet-xxx subnet-yyy \
    --security-group-ids sg-zzz \
    --region ap-northeast-1
```

---

## Step 3: Create Data Source (Aurora MySQL)

### Option A: Via AWS Console

1. Go to QuickSight → **Datasets** → **New dataset**
2. Choose **"RDS"** as data source type
3. Configure:
   - **Data source name**: `Tokyo Beta Aurora Analytics`
   - **Instance ID**: Select `tokyobeta-prod-aurora-cluster`
   - **Database**: `analytics`
   - **Username**: (from Secrets Manager: `tokyobeta-prod-aurora-master`)
   - **Password**: (from Secrets Manager)
   - **VPC connection**: `tokyobeta-aurora-connection`
4. Click **Validate connection**
5. Click **Create data source**

### Option B: Via AWS CLI

```bash
# Get Aurora credentials
AWS_PROFILE=gghouse aws secretsmanager get-secret-value \
    --secret-id tokyobeta-prod-aurora-master \
    --region ap-northeast-1 \
    --query SecretString --output text | jq -r .

# Create data source
AWS_PROFILE=gghouse aws quicksight create-data-source \
    --aws-account-id 343881458651 \
    --data-source-id tokyobeta-aurora-datasource \
    --name "Tokyo Beta Aurora Analytics" \
    --type AURORA \
    --data-source-parameters '{
        "AuroraParameters": {
            "Host": "tokyobeta-prod-aurora-cluster.cluster-cr46qo6y4bbb.ap-northeast-1.rds.amazonaws.com",
            "Port": 3306,
            "Database": "analytics"
        }
    }' \
    --credentials '{
        "CredentialPair": {
            "Username": "admin",
            "Password": "YOUR_PASSWORD_HERE"
        }
    }' \
    --vpc-connection-properties '{
        "VpcConnectionArn": "arn:aws:quicksight:ap-northeast-1:343881458651:vpcConnection/tokyobeta-aurora-connection"
    }' \
    --region ap-northeast-1
```

---

## Step 4: Create Datasets

Create 4 datasets, one for each analytics table:

### Dataset 1: Daily Activity Summary

**Table**: `analytics.daily_activity_summary`

**Key Columns**:
- `activity_date` (Date)
- `tenant_type` (String: Individual/Corporate)
- `applications_count` (Integer)
- `contracts_signed_count` (Integer)
- `moveins_count` (Integer)
- `moveouts_count` (Integer)
- `net_occupancy_change` (Integer)

**Calculated Fields**:
```
# Occupancy Rate (calculated)
occupancy_rate = (active_leases / total_rooms) * 100

# Month-over-Month Growth
mom_growth = (current_month_contracts - previous_month_contracts) / previous_month_contracts * 100
```

### Dataset 2: New Contracts

**Table**: `analytics.new_contracts`

**Key Columns**:
- `contract_date` (Date)
- `asset_id_hj` (String)
- `room_number` (String)
- `tenant_type` (String)
- `monthly_rent` (Decimal)
- `age` (Integer)
- `gender` (String)
- `nationality` (String)
- `latitude` (Decimal)
- `longitude` (Decimal)

**Calculated Fields**:
```
# Age Group
age_group = ifelse(age < 25, "18-24",
             ifelse(age < 35, "25-34",
             ifelse(age < 45, "35-44",
             ifelse(age < 55, "45-54", "55+"))))

# Rent Tier
rent_tier = ifelse(monthly_rent < 50000, "Budget",
             ifelse(monthly_rent < 70000, "Standard",
             ifelse(monthly_rent < 90000, "Premium", "Luxury")))
```

### Dataset 3: Moveouts

**Table**: `analytics.moveouts`

**Key Columns**:
- `moveout_date` (Date)
- `contract_date` (Date)
- `total_stay_months` (Integer)
- `monthly_rent` (Decimal)
- `tenant_type` (String)
- `moveout_reason_id` (Integer)

**Calculated Fields**:
```
# Tenure Category
tenure_category = ifelse(total_stay_months < 6, "Short (<6m)",
                   ifelse(total_stay_months < 12, "Medium (6-12m)",
                   ifelse(total_stay_months < 24, "Long (1-2y)", "Very Long (2y+)")))

# Total Revenue (approximate)
total_revenue = monthly_rent * total_stay_months
```

### Dataset 4: Moveout Notices

**Table**: `analytics.moveout_notices`

**Key Columns**:
- `notice_received_date` (Date)
- `planned_moveout_date` (Date)
- `notice_lead_time_days` (Integer)
- `moveout_status` (String: Pending/Completed)

**Calculated Fields**:
```
# Notice Period Category
notice_period = ifelse(notice_lead_time_days < 14, "Short Notice (<2w)",
                 ifelse(notice_lead_time_days < 30, "Standard (2-4w)",
                 ifelse(notice_lead_time_days < 60, "Long (1-2m)", "Very Long (2m+)")))
```

---

## Step 5: Create Analyses and Dashboards

### Dashboard 1: Executive Summary

**Key Visuals**:
1. **KPI Cards** (Top Row):
   - Total Active Contracts (current)
   - New Contracts (this month)
   - Moveouts (this month)
   - Net Occupancy Change
   - Average Monthly Rent

2. **Line Chart**: Daily activity trends (last 90 days)
   - X-axis: `activity_date`
   - Y-axis: `contracts_signed_count`, `moveins_count`, `moveouts_count`
   - Color: Metric type

3. **Stacked Bar Chart**: Individual vs Corporate split
   - X-axis: Month (from `activity_date`)
   - Y-axis: Count
   - Color: `tenant_type`

4. **Donut Chart**: Current portfolio composition
   - Slice: `tenant_type`
   - Value: Count of active contracts

### Dashboard 2: New Contracts Analysis

**Key Visuals**:
1. **Bar Chart**: Contracts by Age Group
   - X-axis: `age_group` (calculated field)
   - Y-axis: Count
   - Color: `gender`

2. **Horizontal Bar Chart**: Top 10 Nationalities
   - X-axis: Count
   - Y-axis: `nationality`
   - Sort: Descending by count

3. **Heat Map**: Contracts by Month and Rent Tier
   - Rows: Month (from `contract_date`)
   - Columns: `rent_tier` (calculated field)
   - Value: Count

4. **Table**: Recent Contracts (last 30 days)
   - Columns: `contract_date`, `asset_id_hj`, `room_number`, `monthly_rent`, `age`, `nationality`
   - Sort: `contract_date` DESC
   - Limit: 50 rows

### Dashboard 3: Moveout Analysis

**Key Visuals**:
1. **Histogram**: Distribution of Tenure
   - X-axis: `total_stay_months`
   - Y-axis: Frequency
   - Bins: 6 (0-6m, 6-12m, 12-18m, 18-24m, 24-36m, 36m+)

2. **Bar Chart**: Moveouts by Reason
   - X-axis: `moveout_reason_id`
   - Y-axis: Count
   - Color: `tenant_type`

3. **Scatter Plot**: Rent vs Tenure
   - X-axis: `monthly_rent`
   - Y-axis: `total_stay_months`
   - Color: `tenant_type`
   - Size: `total_revenue` (calculated)

4. **Line Chart**: Moveout trend over time
   - X-axis: Month (from `moveout_date`)
   - Y-axis: Count
   - Filter: Last 24 months

### Dashboard 4: Tokyo Map View

**Key Visuals**:
1. **Map (Geospatial)**:
   - Latitude: `latitude`
   - Longitude: `longitude`
   - Color: `monthly_rent` (gradient: blue=low, red=high)
   - Size: Number of contracts
   - Tooltip: `asset_id_hj`, `monthly_rent`, contract count

2. **Heat Map (Density)**:
   - Use QuickSight's geospatial heat map
   - Latitude/Longitude from dataset
   - Intensity: Number of contracts

3. **Bar Chart**: Contracts by Prefecture/Municipality
   - X-axis: `municipality`
   - Y-axis: Count
   - Sort: Descending

4. **Table**: Property Details
   - Columns: `asset_id_hj`, `full_address`, contract count, avg rent, occupancy rate
   - Filter: Clickable from map

---

## Step 6: Share Dashboards with Users

### Create User Groups

1. Go to QuickSight → **Manage QuickSight** → **Manage users**
2. Create groups:
   - `Warburg_PE` (read-only, all dashboards)
   - `JRAM_SPC` (read-only, all dashboards)
   - `Tosei_AM` (read-only, all dashboards)
   - `GGhouse_PM` (read-only + export, all dashboards)

### Invite Users

```bash
# Invite user via CLI
AWS_PROFILE=gghouse aws quicksight create-group-membership \
    --aws-account-id 343881458651 \
    --namespace default \
    --group-name Warburg_PE \
    --member-name user@warburg.com \
    --region ap-northeast-1
```

### Share Dashboards

1. Open each dashboard
2. Click **Share** (top-right)
3. Select user groups
4. Set permissions:
   - **View**: Can see dashboard
   - **Export**: Can download data/PDF (only for GGhouse)

---

## Step 7: Schedule SPICE Refresh (Optional)

If using SPICE (in-memory) instead of Direct Query:

```bash
# Schedule daily refresh at 8:00 AM JST (23:00 UTC previous day)
AWS_PROFILE=gghouse aws quicksight create-ingestion \
    --aws-account-id 343881458651 \
    --data-set-id tokyobeta-daily-activity-dataset \
    --ingestion-id daily-refresh-$(date +%Y%m%d%H%M%S) \
    --region ap-northeast-1
```

Or configure in QuickSight UI:
- Dataset → **Schedule refresh**
- Frequency: Daily at 8:00 AM JST
- Time zone: Asia/Tokyo

---

## Troubleshooting

### Issue: "VPC connection failed"

**Solution**: Verify security group allows inbound on port 3306 from QuickSight's security group.

```bash
# Add ingress rule to Aurora security group
AWS_PROFILE=gghouse aws ec2 authorize-security-group-ingress \
    --group-id sg-aurora \
    --source-group sg-quicksight \
    --protocol tcp \
    --port 3306 \
    --region ap-northeast-1
```

### Issue: "Unknown column in field list"

**Solution**: Refresh dataset schema in QuickSight:
- Dataset → **Edit dataset**
- **Refresh fields** (bottom-left)

### Issue: "Invalid credentials"

**Solution**: Update data source credentials:
- Data sources → Select Aurora data source
- **Edit data source**
- **Edit credentials** → Enter new password

---

## Cost Estimation

### QuickSight Enterprise

- **Authors**: $18/user/month (unlimited dashboards)
  - 4 users (Warburg, JRAM, Tosei, GGhouse) = $72/month

- **Readers**: $0.30/session (max $5/month per reader)
  - If 10 readers × $5/month = $50/month

- **SPICE capacity**: $0.25/GB/month (if used)
  - Current data: ~20MB = $0.01/month

**Total estimated cost**: ~$122/month for 4 authors + 10 readers

---

## References

- [QuickSight Pricing](https://aws.amazon.com/quicksight/pricing/)
- [VPC Connections for QuickSight](https://docs.aws.amazon.com/quicksight/latest/user/working-with-aws-vpc.html)
- [QuickSight User Guide](https://docs.aws.amazon.com/quicksight/latest/user/welcome.html)
- [Geospatial Visualizations](https://docs.aws.amazon.com/quicksight/latest/user/geospatial-visualizations.html)

---

**Next Action**: Enable QuickSight at https://quicksight.aws.amazon.com/ and follow this guide step-by-step.
