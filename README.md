# Tokyo Beta - Real Estate Analytics Dashboard

End-to-end data pipeline from RDS SQL dumps to QuickSight dashboards for property management analytics.

## Overview

This system processes daily SQL dumps from the property management system (PMS), transforms them into analytics-ready tables in Aurora MySQL, and powers interactive dashboards in Amazon QuickSight. The dashboards serve 4 organizations: Warburg (PE), JRAM (SPC), Tosei (Asset Management), and GGhouse (PM Company).

## Architecture

```
S3 (jram-gghouse/dumps/) 
  → Lambda (Daily ETL) 
    → Aurora MySQL (4 Analytics Tables)
      → QuickSight (Interactive Dashboards with Tokyo Map)
```

## Key Features

- **Daily ETL**: Automated data processing triggered daily at 7:00 AM JST
- **4 Analytics Tables**: Daily summary, new contracts, moveouts, moveout notices (24-month rolling window)
- **Tokyo Map Visualization**: Geospatial heatmap with asset-level drill-down using lat/long
- **CSV/Excel Export**: All dashboard visuals exportable for further analysis
- **Multi-organization Access**: Shared dashboards accessible by 4 stakeholder organizations

## Quick Start

### Prerequisites

- AWS Account with admin access (gghouse - 343881458651)
- Terraform >= 1.5.0
- Python >= 3.9
- AWS CLI configured with SSO profile `gghouse`

### Deployment

```bash
# 1. Create Terraform backend (one-time setup)
cd terraform
terraform init
terraform apply -target=aws_s3_bucket.terraform_state

# 2. Deploy infrastructure
cd environments/prod
terraform init
terraform plan -out=tfplan
terraform apply tfplan

# 3. Initialize database schemas
cd ../../../scripts
./init_db.sh

# 4. Deploy Lambda function
cd ../lambda/etl_processor
make deploy

# 5. Test ETL with sample dump
python ../scripts/test_etl_local.py
```

### Directory Structure

```
├── terraform/          # Infrastructure as Code
├── lambda/             # ETL processor (Python)
├── sql/                # Schema definitions and SQL transforms
├── quicksight/         # Dashboard templates
├── docs/               # Architecture and runbooks
├── config/             # Environment configurations
└── scripts/            # Deployment and validation scripts
```

##Dashboard Access

1. Navigate to [QuickSight Console](https://ap-northeast-1.quicksight.aws.amazon.com)
2. Select "Dashboards" from the left menu
3. Available dashboards:
   - Executive Summary
   - New Contracts Analysis
   - Moveout & Retention Analysis
   - Tokyo Map View

## Cost Estimate

- **Aurora MySQL**: ~$120/month (db.t4g.medium x 2)
- **Lambda**: ~$5/month (daily 5-min runs)
- **QuickSight**: ~$90/month (5 Enterprise users)
- **Total**: ~$225/month

## Documentation

- [Architecture Deep-Dive](docs/architecture.md)
- [ETL Transformation Logic](docs/etl_logic.md)
- [Deployment Guide](docs/deployment.md)
- [Operations Runbook](docs/runbook.md)
- [User Guide](docs/user_guide.md)

## Support

For issues or questions, contact the data engineering team.

## License

Proprietary - Internal use only
