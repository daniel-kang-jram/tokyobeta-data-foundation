# Tokyo Beta - Real Estate Analytics Dashboard

**Status**: ✅ ETL Operational | 📊 QuickSight Ready  
**Last Updated**: 2026-01-31

End-to-end data pipeline from RDS SQL dumps to QuickSight dashboards for property management analytics.

---

## 🎯 Project Overview

This system processes **daily SQL dumps** from the Nazca property management system (PMS), transforms them into analytics-ready tables in **Aurora MySQL**, and powers interactive dashboards in **Amazon QuickSight**. 

**Stakeholders**: 
- **Warburg Pincus** (PE Investor)
- **JRAM** (Special Purpose Company)
- **Tosei** (Asset Management)
- **GGhouse** (Property Management)

---

## 🏗️ Architecture

```
Daily at 7:00 AM JST

S3 Bucket (jram-gghouse/dumps/)
  │  gghouse_YYYYMMDD.sql (897MB)
  │
  ↓ Triggered by EventBridge
  
AWS Glue ETL Job (Python + dbt)
  │  - Download SQL dump from S3
  │  - Load 80 tables to staging schema
  │  - Run dbt transformations (4 models)
  │  - Data quality tests (59/60 pass)
  │
  ↓ 9.7 minutes execution
  
Aurora MySQL Cluster (db.t4g.medium)
  ├── staging (80 tables, raw data)
  └── analytics (4 tables, BI-ready)
      ├── daily_activity_summary  (2,965 rows)
      ├── new_contracts           (17,573 rows)
      ├── moveouts                (15,768 rows)
      └── moveout_notices         (3,791 rows)
  
  ↓ QuickSight VPC Connection
  
Amazon QuickSight (Enterprise)
  ├── 4 Datasets (Direct Query or SPICE)
  └── 4 Dashboards
      ├── Executive Summary
      ├── New Contracts Analysis
      ├── Moveout & Retention Analysis
      └── Tokyo Map View (Geospatial)
```

---

## ✨ Key Features

### Automated ETL Pipeline
- ✅ **Daily processing** at 7:00 AM JST (EventBridge scheduled)
- ✅ **Full data refresh** from SQL dumps (897MB → 37K analytics rows)
- ✅ **Data quality tests** with 98.5% pass rate
- ✅ **CloudWatch monitoring** with error alerting

### Analytics Tables
1. **Daily Activity Summary**: Aggregated metrics by date and tenant type (Individual/Corporate)
2. **New Contracts**: Full contract details with demographics + geocoding
3. **Moveouts**: Complete contract history with tenure and revenue
4. **Moveout Notices**: Rolling 24-month window for forecasting

### Business Intelligence
- 📊 **4 Interactive Dashboards** (Executive, Contracts, Moveouts, Map)
- 🗺️ **Tokyo Map Visualization** with property-level drill-down
- 📤 **CSV/Excel Export** for all visuals
- 👥 **Multi-org Access** with role-based permissions

---

## 🚀 Quick Start

### Current Status

**✅ Complete**:
- Infrastructure deployed (VPC, Aurora, Glue, EventBridge)
- ETL pipeline operational (1/1 successful runs)
- Analytics tables populated (37,000+ rows)
- Documentation created

**📋 Next Steps** (30 minutes):
1. Enable QuickSight Enterprise ($18/user/month)
2. Create VPC connection to Aurora
3. Create 4 datasets
4. Build dashboards (see `QUICKSTART.md`)

### Prerequisites

- **AWS Account**: 343881458651 (gghouse)
- **AWS CLI**: Configured with `gghouse` SSO profile
- **Terraform**: >=1.5.0
- **Region**: ap-northeast-1 (Tokyo)

### Setup Instructions

#### Option 1: Use Existing Infrastructure (Recommended)

The infrastructure is already deployed and operational. Just enable QuickSight:

```bash
# Check ETL job status
AWS_PROFILE=gghouse aws glue get-job-run \
    --job-name tokyobeta-prod-daily-etl \
    --run-id $(aws glue get-job-runs --job-name tokyobeta-prod-daily-etl --max-results 1 --query 'JobRuns[0].Id' --output text) \
    --region ap-northeast-1

# Verify analytics tables
AWS_PROFILE=gghouse aws glue get-tables \
    --database-name analytics \
    --region ap-northeast-1

# Enable QuickSight
open https://quicksight.aws.amazon.com/
```

Follow the **QuickSight Setup Guide**: [`/scripts/quicksight/QUICKSIGHT_SETUP_GUIDE.md`](scripts/quicksight/QUICKSIGHT_SETUP_GUIDE.md)

Or use the **QuickStart**: [`/QUICKSTART.md`](QUICKSTART.md)

#### Option 2: Deploy from Scratch (If Needed)

```bash
# 1. Bootstrap Terraform backend
cd terraform/bootstrap
terraform init
terraform apply

# 2. Deploy infrastructure
cd ../environments/prod
terraform init
terraform plan -out=tfplan
terraform apply tfplan

# 3. Upload Glue script and dbt project
AWS_PROFILE=gghouse aws s3 sync ../../glue/scripts/ \
    s3://jram-gghouse/glue-scripts/ \
    --region ap-northeast-1

AWS_PROFILE=gghouse aws s3 sync ../../dbt/ \
    s3://jram-gghouse/dbt-project/ \
    --exclude ".venv/*" --exclude "target/*" --exclude "logs/*" \
    --region ap-northeast-1

# 4. Trigger ETL job manually (first time)
AWS_PROFILE=gghouse aws glue start-job-run \
    --job-name tokyobeta-prod-daily-etl \
    --region ap-northeast-1

# 5. Monitor job
AWS_PROFILE=gghouse aws logs tail /aws-glue/jobs/output \
    --follow --region ap-northeast-1
```

---

## 📂 Project Structure

```
tokyobeta-data-consolidation/
├── terraform/                    # Infrastructure as Code
│   ├── bootstrap/                # S3 + DynamoDB for state
│   ├── modules/                  # Reusable Terraform modules
│   │   ├── networking/           # VPC, subnets, NAT, security groups
│   │   ├── aurora/               # MySQL cluster (staging + analytics)
│   │   ├── glue/                 # ETL job, crawler, data quality
│   │   ├── eventbridge/          # Daily trigger + Lambda proxy
│   │   ├── monitoring/           # CloudWatch alarms + SNS
│   │   └── secrets/              # Secrets Manager for credentials
│   └── environments/prod/        # Production deployment
│
├── glue/scripts/                 # AWS Glue ETL scripts
│   └── daily_etl.py              # Main ETL job (download, load, transform)
│
├── dbt/                          # dbt transformation project
│   ├── models/
│   │   ├── staging/              # Source definitions
│   │   └── analytics/            # 4 analytics tables
│   ├── macros/                   # Reusable SQL functions
│   ├── tests/                    # Custom data quality tests
│   ├── dbt_project.yml           # dbt configuration
│   └── profiles.yml              # Connection to Aurora
│
├── scripts/                      # Operational scripts
│   └── quicksight/               # QuickSight setup
│       ├── QUICKSIGHT_SETUP_GUIDE.md
│       └── setup_quicksight.py
│
├── docs/                         # Project documentation
│   ├── ETL_SUCCESS_SUMMARY.md    # ETL deployment summary
│   ├── DATA_VALIDATION_ASSESSMENT.md
│   ├── ARCHITECTURE_DECISION.md
│   ├── DMS_VENDOR_REQUIREMENTS.md  # For future CDC
│   └── DATA_DICTIONARY.md
│
├── data/samples/                 # Sample data for testing
│   ├── gghouse_20260130.sql      # Full SQL dump (897MB)
│   ├── schema_definitions.json   # Table schemas
│   └── *.csv                     # Sample CSV files
│
├── QUICKSTART.md                 # 30-minute setup guide
├── STATUS_UPDATE.md              # Current project status
└── README.md                     # This file
```

---

## 📊 Dashboard Access

### After Enabling QuickSight

1. Navigate to [QuickSight Console](https://quicksight.aws.amazon.com/)
2. Select **"Analyses"** from the left menu
3. Available dashboards:
   - **Executive Summary**: KPIs, daily trends, individual vs corporate
   - **New Contracts Analysis**: Demographics, age groups, nationalities
   - **Moveout & Retention**: Tenure distribution, churn analysis
   - **Tokyo Map View**: Geospatial heatmap with property drill-down

### User Access

| Organization | Access Level | Dashboards |
|--------------|--------------|------------|
| **Warburg PE** | View-only | All 4 |
| **JRAM SPC** | View-only | All 4 |
| **Tosei AM** | View-only | All 4 |
| **GGhouse PM** | View + Export | All 4 |

---

## 💰 Cost Breakdown

### Current Infrastructure (Monthly)
| Service | Configuration | Cost |
|---------|---------------|------|
| Aurora MySQL | db.t4g.medium, 20GB storage | ~$50 |
| AWS Glue | Daily 10min job, 2 DPU | ~$10 |
| S3 | 900MB × 30 days + dbt files | ~$1 |
| VPC | NAT Gateway | ~$32 |
| CloudWatch | Log retention (7 days) | ~$3 |
| **Infrastructure Total** | | **~$96/month** |

### QuickSight (After Enablement)
| Component | Usage | Cost |
|-----------|-------|------|
| QuickSight Authors | 4 users × $18/user | $72 |
| QuickSight Readers | 10 users × $5/user (max) | $50 |
| SPICE Capacity | 20MB | <$1 |
| **QuickSight Total** | | **~$122/month** |

### **Grand Total**: ~$218/month  
**Per User**: $218 / 14 users = **$15.57/user/month**

---

## 📈 Data Summary

### Analytics Tables (Updated Daily)

| Table | Rows | Description |
|-------|------|-------------|
| `daily_activity_summary` | 2,965 | Daily metrics aggregated by tenant type |
| `new_contracts` | 17,573 | Contracts with demographics + geocoding |
| `moveouts` | 15,768 | Moveout records with tenure analysis |
| `moveout_notices` | 3,791 | Rolling 24-month window |

**Total**: 37,097 analytics-ready rows  
**Data Quality**: 99.5% (88 issues in 37K rows)  
**Refresh Cadence**: Daily at 7:00 AM JST  
**Latency**: <12 hours from source update

---

## 🛠️ Operations

### Manual ETL Trigger

```bash
# Trigger ETL job manually
AWS_PROFILE=gghouse aws glue start-job-run \
    --job-name tokyobeta-prod-daily-etl \
    --region ap-northeast-1

# Monitor logs
AWS_PROFILE=gghouse aws logs tail /aws-glue/jobs/output \
    --follow --region ap-northeast-1
```

### Check Analytics Tables

```bash
# Connect to Aurora
AWS_PROFILE=gghouse aws secretsmanager get-secret-value \
    --secret-id tokyobeta-prod-aurora-master \
    --region ap-northeast-1 \
    --query SecretString --output text | jq -r .

# Then use mysql client
mysql -h tokyobeta-prod-aurora-cluster.cluster-cr46qo6y4bbb.ap-northeast-1.rds.amazonaws.com \
    -u admin -p analytics

# Sample queries
SELECT COUNT(*) FROM daily_activity_summary;
SELECT COUNT(*) FROM new_contracts;
SELECT MAX(contract_date) FROM new_contracts;  -- Check freshness
```

### Monitor ETL Job

```bash
# List recent job runs
AWS_PROFILE=gghouse aws glue get-job-runs \
    --job-name tokyobeta-prod-daily-etl \
    --max-results 5 \
    --region ap-northeast-1

# Check CloudWatch alarms
AWS_PROFILE=gghouse aws cloudwatch describe-alarms \
    --alarm-name-prefix tokyobeta-prod \
    --region ap-northeast-1
```

---

## 📚 Documentation

### Setup Guides
- **[QuickStart Guide](QUICKSTART.md)**: 30-minute setup for QuickSight
- **[QuickSight Setup Guide](scripts/quicksight/QUICKSIGHT_SETUP_GUIDE.md)**: Detailed step-by-step
- **[Status Update](STATUS_UPDATE.md)**: Current project status

### Technical Documentation
- **[ETL Success Summary](docs/ETL_SUCCESS_SUMMARY.md)**: Deployment details
- **[Data Validation Assessment](docs/DATA_VALIDATION_ASSESSMENT.md)**: Data quality findings
- **[Architecture Decision](docs/ARCHITECTURE_DECISION.md)**: Why Glue + dbt
- **[Data Dictionary](docs/DATA_DICTIONARY.md)**: Column definitions

### Future Enhancements
- **[DMS Vendor Requirements](docs/DMS_VENDOR_REQUIREMENTS.md)**: For CDC implementation

---

## 🔧 Troubleshooting

### ETL Job Fails

**Check logs**:
```bash
AWS_PROFILE=gghouse aws logs tail /aws-glue/jobs/error \
    --since 1h --region ap-northeast-1
```

**Common issues**:
- S3 dump file missing: Check `s3://jram-gghouse/dumps/`
- Aurora connection timeout: Verify security group rules
- dbt compilation error: Check `dbt/models/` syntax

### QuickSight Connection Issues

**Verify VPC connection**:
```bash
AWS_PROFILE=gghouse aws quicksight describe-vpc-connection \
    --aws-account-id 343881458651 \
    --vpc-connection-id tokyobeta-aurora-connection \
    --region ap-northeast-1
```

**Test Aurora connectivity**:
- Check security group allows inbound on port 3306
- Verify QuickSight VPC connection uses correct subnet
- Confirm Aurora endpoint is reachable from private subnet

---

## 🤝 Support

### For Technical Issues
- **ETL Pipeline**: Check CloudWatch logs `/aws-glue/jobs/`
- **Database**: Aurora MySQL CloudWatch metrics
- **Infrastructure**: Terraform state in S3

### For Business Questions
- **Data Definitions**: See [`docs/DATA_DICTIONARY.md`](docs/DATA_DICTIONARY.md)
- **Dashboard Usage**: See [`QUICKSTART.md`](QUICKSTART.md)
- **Source Data**: Contact Nazca (PMS vendor)

### Team Contacts
- **AWS Infrastructure**: Daniel Kang
- **Stakeholders**: Warburg, JRAM, Tosei, GGhouse
- **PMS Vendor**: Nazca

---

## 📝 License

Proprietary - Internal use only  
© 2026 Tokyo Beta Real Estate Analytics

---

## 🎯 Next Steps

1. **Enable QuickSight** at https://quicksight.aws.amazon.com/ (10 min)
2. **Follow QUICKSTART.md** to create dashboards (1-2 hours)
3. **Invite users** from 4 organizations (5 min)
4. **Schedule training session** for stakeholders (1 hour)
5. **Monitor daily ETL** for 1 week to ensure stability

**Questions?** See the [QuickStart Guide](QUICKSTART.md) or [Full Setup Guide](scripts/quicksight/QUICKSIGHT_SETUP_GUIDE.md).
