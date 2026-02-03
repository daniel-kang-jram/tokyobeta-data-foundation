# QuickStart: Tokyo Beta BI Dashboard

**🎉 ETL Pipeline: OPERATIONAL ✅**  
**📊 QuickSight: Ready to Enable**

---

## What's Working Right Now

### ✅ Automated Daily ETL
- **Runs**: Every day at 7:00 AM JST
- **Source**: S3 dumps from Nazca PMS
- **Output**: 4 analytics tables in Aurora MySQL
- **Data**: 37,000+ rows of clean, analytics-ready data

### ✅ Analytics Tables Available
```
analytics.daily_activity_summary  →  2,965 rows  (daily metrics)
analytics.new_contracts           →  17,573 rows (with demographics)
analytics.moveouts                →  15,768 rows (full history)
analytics.moveout_notices         →  3,791 rows  (24-month window)
```

---

## 🚀 Quick Setup (30 minutes total)

### Step 1: Enable QuickSight (10 min)

**Open**: https://quicksight.aws.amazon.com/

**Choose**:
- ✅ Enterprise edition
- ✅ Enable VPC access
- ✅ Region: ap-northeast-1

**Cost**: $18/user/month (4 users = $72/month)

---

### Step 2: Create VPC Connection (5 min)

**In QuickSight Console**:

```
Manage QuickSight → VPC connections → Add VPC connection

Name: tokyobeta-aurora-connection
VPC: tokyobeta-prod-vpc
Subnet: private-subnet-1 (where Aurora is)
Security Group: tokyobeta-prod-aurora-sg
```

---

### Step 3: Connect to Aurora (5 min)

**In QuickSight Console**:

```
Datasets → New dataset → RDS

Data source name: Tokyo Beta Aurora Analytics
Instance: tokyobeta-prod-aurora-cluster
Database: analytics
VPC connection: tokyobeta-aurora-connection

Get credentials from AWS Secrets Manager:
  Secret: tokyobeta-prod-aurora-master
  
Click "Validate connection" → Should succeed
```

---

### Step 4: Create Datasets (10 min)

**Create 4 datasets from these tables**:

1. `analytics.daily_activity_summary`
2. `analytics.new_contracts`
3. `analytics.moveouts`
4. `analytics.moveout_notices`

**For each dataset**:
- Click **"Use custom SQL"** (optional, for advanced queries)
- Or select table directly
- Click **"Edit/Preview data"** to add calculated fields
- Click **"Save & publish"**

---

## 📊 Pre-built Dashboard Templates

### Dashboard 1: Executive Summary (1 hour to build)

**KPIs** (Top row):
```
Total Active Contracts | New This Month | Moveouts This Month | Net Change | Avg Rent
```

**Charts**:
- Line: Daily activity trends (90 days)
- Stacked Bar: Individual vs Corporate split
- Donut: Portfolio composition

**Filters**:
- Date range
- Tenant type (Individual/Corporate)
- Property (asset_id_hj)

---

### Dashboard 2: New Contracts (1 hour to build)

**Charts**:
- Bar: Contracts by age group (18-24, 25-34, 35-44, 45-54, 55+)
- Horizontal Bar: Top 10 nationalities
- Heat Map: Contracts by month × rent tier
- Table: Recent contracts (last 30 days)

**Calculated Fields**:
```sql
age_group = ifelse(age < 25, "18-24",
             ifelse(age < 35, "25-34",
             ifelse(age < 45, "35-44",
             ifelse(age < 55, "45-54", "55+"))))

rent_tier = ifelse(monthly_rent < 50000, "Budget",
             ifelse(monthly_rent < 70000, "Standard",
             ifelse(monthly_rent < 90000, "Premium", "Luxury")))
```

---

### Dashboard 3: Moveout Analysis (1 hour to build)

**Charts**:
- Histogram: Tenure distribution (0-6m, 6-12m, 12-18m, 18-24m, 24m+)
- Bar: Moveouts by reason
- Scatter: Rent vs Tenure (colored by tenant type)
- Line: Moveout trend (last 24 months)

**Calculated Fields**:
```sql
tenure_category = ifelse(total_stay_months < 6, "Short (<6m)",
                   ifelse(total_stay_months < 12, "Medium (6-12m)",
                   ifelse(total_stay_months < 24, "Long (1-2y)", "Very Long (2y+)")))

total_revenue = monthly_rent * total_stay_months
```

---

### Dashboard 4: Tokyo Map (1 hour to build)

**Visuals**:
- **Geospatial Map**: Properties on Tokyo map
  - Latitude: `latitude`
  - Longitude: `longitude`
  - Color: `monthly_rent` (blue=low, red=high)
  - Size: Number of contracts

- **Bar Chart**: Contracts by municipality
- **Table**: Property details (clickable from map)

**Note**: Exclude 629 rows with invalid geocoding:
```sql
WHERE latitude BETWEEN 35.5 AND 35.9
  AND longitude BETWEEN 139.5 AND 140.0
```

---

## 👥 User Management

### Create 4 Groups

```
Warburg_PE      →  Read-only, all dashboards
JRAM_SPC        →  Read-only, all dashboards
Tosei_AM        →  Read-only, all dashboards
GGhouse_PM      →  Read + Export, all dashboards
```

### Invite Users

**In QuickSight Console**:
```
Manage QuickSight → Manage users → Invite users

Enter emails:
- user1@warburg.com       → Assign to Warburg_PE
- user2@jram.com          → Assign to JRAM_SPC
- user3@tosei.com         → Assign to Tosei_AM
- user4@gghouse.co.jp     → Assign to GGhouse_PM
```

### Share Dashboards

For each dashboard:
```
Dashboard → Share → Add users/groups
  
  Warburg_PE, JRAM_SPC, Tosei_AM  →  View only
  GGhouse_PM                       →  View + Export
```

---

## 🛠️ Troubleshooting

### "Can't connect to Aurora"

**Check**:
1. VPC connection status: Should be "Available"
2. Security group: Should allow port 3306 from QuickSight SG
3. Credentials: Get latest from Secrets Manager

**Fix**:
```bash
# Get Aurora credentials
AWS_PROFILE=gghouse aws secretsmanager get-secret-value \
    --secret-id tokyobeta-prod-aurora-master \
    --region ap-northeast-1 \
    --query SecretString --output text | jq -r .

# Test connection from EC2 (if needed)
mysql -h tokyobeta-prod-aurora-cluster.cluster-cr46qo6y4bbb.ap-northeast-1.rds.amazonaws.com \
    -u admin -p analytics
```

---

### "Dataset shows no data"

**Check**:
1. Table exists: `SELECT COUNT(*) FROM analytics.new_contracts;`
2. Dataset refresh: QuickSight → Dataset → Refresh now
3. Permissions: Data source has correct IAM role

**Fix**: Re-create dataset with correct table name

---

### "Map not showing locations"

**Check**:
1. Latitude/Longitude fields are mapped correctly
2. Filter out invalid coordinates (outside Tokyo)

**Fix**: Add calculated field:
```sql
valid_location = ifelse(
    latitude >= 35.5 AND latitude <= 35.9 AND
    longitude >= 139.5 AND longitude <= 140.0,
    "Valid", "Invalid"
)

Then filter: valid_location = "Valid"
```

---

## 💡 Pro Tips

### Performance Optimization
- **Direct Query**: Real-time data, slower queries
- **SPICE**: In-memory, faster queries, requires refresh
- **Recommendation**: Use SPICE for <1M rows, Direct Query for >1M

### Refresh Schedule
```
Datasets → Schedule refresh
  
  Frequency: Daily
  Time: 8:00 AM JST (after ETL completes at 7:00 AM)
  Time zone: Asia/Tokyo
```

### Email Subscriptions
```
Dashboard → Share → Email report

  Recipients: stakeholder-group@company.com
  Schedule: Weekly on Monday, 9:00 AM JST
  Format: PDF
```

### Mobile Access
- QuickSight has iOS and Android apps
- Dashboards are mobile-responsive
- Users can view (not edit) on mobile

---

## 📚 Full Documentation

- **Detailed Setup**: `/scripts/quicksight/QUICKSIGHT_SETUP_GUIDE.md`
- **ETL Summary**: `/docs/ETL_SUCCESS_SUMMARY.md`
- **Status Update**: `/STATUS_UPDATE.md`
- **Data Dictionary**: `/docs/DATA_DICTIONARY.md`

---

## 🆘 Support

### For Technical Issues
- Check CloudWatch logs: `/aws-glue/jobs/output`
- Review ETL status: AWS Glue console
- Database issues: Aurora MySQL logs

### For Business Questions
- Data definitions: See `DATA_DICTIONARY.md`
- Calculation formulas: See dashboard descriptions above
- Source data issues: Contact Nazca (PMS vendor)

---

## 🎯 Success Checklist

- [ ] QuickSight enabled (Enterprise edition)
- [ ] VPC connection created
- [ ] Aurora data source connected
- [ ] 4 datasets created
- [ ] Executive Summary dashboard built
- [ ] New Contracts dashboard built
- [ ] Moveout Analysis dashboard built
- [ ] Tokyo Map dashboard built
- [ ] Users invited and assigned to groups
- [ ] Dashboards shared with groups
- [ ] Training session scheduled with stakeholders
- [ ] Email subscriptions configured

---

**Ready to get started?** 🚀

1. Go to https://quicksight.aws.amazon.com/
2. Click "Sign up for QuickSight"
3. Follow steps 1-4 above
4. Start building dashboards!

**Questions?** See the full setup guide: `/scripts/quicksight/QUICKSIGHT_SETUP_GUIDE.md`
