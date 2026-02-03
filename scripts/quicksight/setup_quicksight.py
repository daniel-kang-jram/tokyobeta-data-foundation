#!/usr/bin/env python3
"""
QuickSight Setup Script
Creates data source, datasets, analyses, and dashboards for Tokyo Beta Real Estate BI

Usage:
    python setup_quicksight.py --aws-account-id 343881458651 --region ap-northeast-1
"""

import boto3
import json
import time
import argparse
from typing import Dict, List, Any


class QuickSightSetup:
    def __init__(self, aws_account_id: str, region: str = 'ap-northeast-1'):
        self.aws_account_id = aws_account_id
        self.region = region
        self.quicksight = boto3.client('quicksight', region_name=region)
        self.secretsmanager = boto3.client('secretsmanager', region_name=region)
        self.namespace = 'default'
        
        # QuickSight resource IDs
        self.data_source_id = 'tokyobeta-aurora-datasource'
        self.dataset_ids = {
            'daily_activity': 'tokyobeta-daily-activity-dataset',
            'new_contracts': 'tokyobeta-new-contracts-dataset',
            'moveouts': 'tokyobeta-moveouts-dataset',
            'moveout_notices': 'tokyobeta-moveout-notices-dataset'
        }
        
    def get_aurora_credentials(self) -> Dict[str, str]:
        """Retrieve Aurora credentials from Secrets Manager"""
        print("📦 Retrieving Aurora credentials from Secrets Manager...")
        
        secret = self.secretsmanager.get_secret_value(
            SecretId='tokyobeta-prod-aurora-master'
        )
        creds = json.loads(secret['SecretString'])
        
        return {
            'host': creds['host'],
            'port': creds['port'],
            'username': creds['username'],
            'password': creds['password'],
            'database': 'analytics'
        }
    
    def check_quicksight_subscription(self) -> bool:
        """Check if QuickSight is enabled for this AWS account"""
        print("🔍 Checking QuickSight subscription status...")
        
        try:
            response = self.quicksight.describe_account_subscription(
                AwsAccountId=self.aws_account_id
            )
            edition = response['AccountInfo']['Edition']
            status = response['AccountInfo']['AccountSubscriptionStatus']
            print(f"✅ QuickSight is enabled: {edition} edition, status: {status}")
            return True
        except self.quicksight.exceptions.ResourceNotFoundException:
            print("❌ QuickSight is not enabled for this account")
            print("👉 Please enable QuickSight at: https://quicksight.aws.amazon.com/")
            return False
    
    def create_data_source(self, aurora_creds: Dict[str, str]) -> bool:
        """Create QuickSight data source for Aurora MySQL"""
        print(f"\n📊 Creating QuickSight data source: {self.data_source_id}...")
        
        try:
            # Check if data source already exists
            try:
                self.quicksight.describe_data_source(
                    AwsAccountId=self.aws_account_id,
                    DataSourceId=self.data_source_id
                )
                print(f"ℹ️  Data source '{self.data_source_id}' already exists, updating...")
                
                # Update existing data source
                self.quicksight.update_data_source(
                    AwsAccountId=self.aws_account_id,
                    DataSourceId=self.data_source_id,
                    Name='Tokyo Beta Aurora Analytics',
                    DataSourceParameters={
                        'AuroraParameters': {
                            'Host': aurora_creds['host'],
                            'Port': aurora_creds['port'],
                            'Database': aurora_creds['database']
                        }
                    },
                    Credentials={
                        'CredentialPair': {
                            'Username': aurora_creds['username'],
                            'Password': aurora_creds['password']
                        }
                    },
                    VpcConnectionProperties={
                        'VpcConnectionArn': self._get_vpc_connection_arn()
                    }
                )
                print("✅ Data source updated successfully")
                return True
                
            except self.quicksight.exceptions.ResourceNotFoundException:
                # Create new data source
                response = self.quicksight.create_data_source(
                    AwsAccountId=self.aws_account_id,
                    DataSourceId=self.data_source_id,
                    Name='Tokyo Beta Aurora Analytics',
                    Type='AURORA',
                    DataSourceParameters={
                        'AuroraParameters': {
                            'Host': aurora_creds['host'],
                            'Port': aurora_creds['port'],
                            'Database': aurora_creds['database']
                        }
                    },
                    Credentials={
                        'CredentialPair': {
                            'Username': aurora_creds['username'],
                            'Password': aurora_creds['password']
                        }
                    },
                    Permissions=[
                        {
                            'Principal': f'arn:aws:quicksight:{self.region}:{self.aws_account_id}:user/default/Admin',
                            'Actions': [
                                'quicksight:DescribeDataSource',
                                'quicksight:DescribeDataSourcePermissions',
                                'quicksight:PassDataSource',
                                'quicksight:UpdateDataSource',
                                'quicksight:DeleteDataSource',
                                'quicksight:UpdateDataSourcePermissions'
                            ]
                        }
                    ],
                    VpcConnectionProperties={
                        'VpcConnectionArn': self._get_vpc_connection_arn()
                    }
                )
                print(f"✅ Data source created: {response['Arn']}")
                return True
                
        except Exception as e:
            print(f"❌ Failed to create/update data source: {e}")
            return False
    
    def _get_vpc_connection_arn(self) -> str:
        """Get or create VPC connection for QuickSight"""
        # This would need to be created manually or via Terraform first
        # Format: arn:aws:quicksight:region:account-id:vpcConnection/vpc-connection-id
        vpc_connection_id = 'tokyobeta-vpc-connection'
        return f'arn:aws:quicksight:{self.region}:{self.aws_account_id}:vpcConnection/{vpc_connection_id}'
    
    def create_dataset(self, dataset_key: str, table_name: str, columns: List[Dict]) -> bool:
        """Create a QuickSight dataset"""
        dataset_id = self.dataset_ids[dataset_key]
        dataset_name = table_name.replace('_', ' ').title()
        
        print(f"\n📋 Creating dataset: {dataset_name} ({dataset_id})...")
        
        try:
            # Check if dataset exists
            try:
                self.quicksight.describe_data_set(
                    AwsAccountId=self.aws_account_id,
                    DataSetId=dataset_id
                )
                print(f"ℹ️  Dataset '{dataset_id}' already exists, skipping...")
                return True
            except self.quicksight.exceptions.ResourceNotFoundException:
                pass
            
            # Physical table definition
            physical_table = {
                'RelationalTable': {
                    'DataSourceArn': self._get_data_source_arn(),
                    'Schema': 'analytics',
                    'Name': table_name,
                    'InputColumns': columns
                }
            }
            
            response = self.quicksight.create_data_set(
                AwsAccountId=self.aws_account_id,
                DataSetId=dataset_id,
                Name=dataset_name,
                PhysicalTableMap={
                    f'{table_name}_physical': physical_table
                },
                LogicalTableMap={
                    f'{table_name}_logical': {
                        'Alias': dataset_name,
                        'Source': {
                            'PhysicalTableId': f'{table_name}_physical'
                        }
                    }
                },
                ImportMode='DIRECT_QUERY',  # Use DIRECT_QUERY for real-time data
                Permissions=[
                    {
                        'Principal': f'arn:aws:quicksight:{self.region}:{self.aws_account_id}:user/default/Admin',
                        'Actions': [
                            'quicksight:DescribeDataSet',
                            'quicksight:DescribeDataSetPermissions',
                            'quicksight:PassDataSet',
                            'quicksight:DescribeIngestion',
                            'quicksight:ListIngestions',
                            'quicksight:UpdateDataSet',
                            'quicksight:DeleteDataSet',
                            'quicksight:CreateIngestion',
                            'quicksight:CancelIngestion',
                            'quicksight:UpdateDataSetPermissions'
                        ]
                    }
                ]
            )
            
            print(f"✅ Dataset created: {response['Arn']}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to create dataset '{dataset_id}': {e}")
            return False
    
    def _get_data_source_arn(self) -> str:
        """Get the data source ARN"""
        return f'arn:aws:quicksight:{self.region}:{self.aws_account_id}:datasource/{self.data_source_id}'
    
    def create_all_datasets(self) -> bool:
        """Create all 4 datasets"""
        print("\n" + "="*60)
        print("CREATING QUICKSIGHT DATASETS")
        print("="*60)
        
        # Dataset 1: Daily Activity Summary
        daily_activity_columns = [
            {'Name': 'activity_date', 'Type': 'DATETIME'},
            {'Name': 'tenant_type', 'Type': 'STRING'},
            {'Name': 'applications_count', 'Type': 'INTEGER'},
            {'Name': 'contracts_signed_count', 'Type': 'INTEGER'},
            {'Name': 'moveins_count', 'Type': 'INTEGER'},
            {'Name': 'moveouts_count', 'Type': 'INTEGER'},
            {'Name': 'net_occupancy_change', 'Type': 'INTEGER'},
            {'Name': 'created_at', 'Type': 'DATETIME'},
            {'Name': 'updated_at', 'Type': 'DATETIME'}
        ]
        
        # Dataset 2: New Contracts
        new_contracts_columns = [
            {'Name': 'contract_id', 'Type': 'INTEGER'},
            {'Name': 'tenant_id', 'Type': 'INTEGER'},
            {'Name': 'asset_id_hj', 'Type': 'STRING'},
            {'Name': 'room_number', 'Type': 'STRING'},
            {'Name': 'contract_system', 'Type': 'INTEGER'},
            {'Name': 'contract_channel', 'Type': 'INTEGER'},
            {'Name': 'original_contract_date', 'Type': 'DATETIME'},
            {'Name': 'contract_date', 'Type': 'DATETIME'},
            {'Name': 'contract_start_date', 'Type': 'DATETIME'},
            {'Name': 'rent_start_date', 'Type': 'DATETIME'},
            {'Name': 'contract_expiration_date', 'Type': 'DATETIME'},
            {'Name': 'renewal_flag', 'Type': 'STRING'},
            {'Name': 'monthly_rent', 'Type': 'DECIMAL'},
            {'Name': 'tenant_type', 'Type': 'STRING'},
            {'Name': 'gender', 'Type': 'STRING'},
            {'Name': 'age', 'Type': 'INTEGER'},
            {'Name': 'nationality', 'Type': 'STRING'},
            {'Name': 'occupation_company', 'Type': 'STRING'},
            {'Name': 'residence_status', 'Type': 'STRING'},
            {'Name': 'latitude', 'Type': 'DECIMAL'},
            {'Name': 'longitude', 'Type': 'DECIMAL'},
            {'Name': 'prefecture', 'Type': 'STRING'},
            {'Name': 'municipality', 'Type': 'STRING'},
            {'Name': 'full_address', 'Type': 'STRING'},
            {'Name': 'created_at', 'Type': 'DATETIME'},
            {'Name': 'updated_at', 'Type': 'DATETIME'}
        ]
        
        # Dataset 3: Moveouts
        moveouts_columns = new_contracts_columns + [
            {'Name': 'cancellation_notice_date', 'Type': 'DATETIME'},
            {'Name': 'moveout_date', 'Type': 'DATETIME'},
            {'Name': 'total_stay_days', 'Type': 'INTEGER'},
            {'Name': 'total_stay_months', 'Type': 'INTEGER'},
            {'Name': 'moveout_reason_id', 'Type': 'INTEGER'}
        ]
        
        # Dataset 4: Moveout Notices
        moveout_notices_columns = new_contracts_columns + [
            {'Name': 'notice_received_date', 'Type': 'DATETIME'},
            {'Name': 'planned_moveout_date', 'Type': 'DATETIME'},
            {'Name': 'notice_lead_time_days', 'Type': 'INTEGER'},
            {'Name': 'moveout_status', 'Type': 'STRING'}
        ]
        
        success = True
        success &= self.create_dataset('daily_activity', 'daily_activity_summary', daily_activity_columns)
        success &= self.create_dataset('new_contracts', 'new_contracts', new_contracts_columns)
        success &= self.create_dataset('moveouts', 'moveouts', moveouts_columns)
        success &= self.create_dataset('moveout_notices', 'moveout_notices', moveout_notices_columns)
        
        return success
    
    def list_quicksight_resources(self):
        """List all QuickSight resources for verification"""
        print("\n" + "="*60)
        print("QUICKSIGHT RESOURCES SUMMARY")
        print("="*60)
        
        try:
            # List data sources
            data_sources = self.quicksight.list_data_sources(
                AwsAccountId=self.aws_account_id
            )
            print(f"\n📊 Data Sources ({len(data_sources.get('DataSources', []))}):")
            for ds in data_sources.get('DataSources', []):
                print(f"  - {ds['Name']} ({ds['DataSourceId']}): {ds['Status']}")
            
            # List datasets
            datasets = self.quicksight.list_data_sets(
                AwsAccountId=self.aws_account_id
            )
            print(f"\n📋 Datasets ({len(datasets.get('DataSetSummaries', []))}):")
            for ds in datasets.get('DataSetSummaries', []):
                print(f"  - {ds['Name']} ({ds['DataSetId']})")
            
        except Exception as e:
            print(f"❌ Failed to list resources: {e}")
    
    def run_setup(self):
        """Run the complete QuickSight setup"""
        print("="*60)
        print("TOKYO BETA QUICKSIGHT SETUP")
        print("="*60)
        print(f"AWS Account: {self.aws_account_id}")
        print(f"Region: {self.region}")
        print("="*60)
        
        # Step 1: Check QuickSight subscription
        if not self.check_quicksight_subscription():
            return False
        
        # Step 2: Get Aurora credentials
        aurora_creds = self.get_aurora_credentials()
        
        # Step 3: Create data source
        if not self.create_data_source(aurora_creds):
            return False
        
        # Wait for data source to be ready
        print("\n⏳ Waiting for data source to be ready...")
        time.sleep(5)
        
        # Step 4: Create datasets
        if not self.create_all_datasets():
            return False
        
        # Step 5: Summary
        self.list_quicksight_resources()
        
        print("\n" + "="*60)
        print("✅ QUICKSIGHT SETUP COMPLETED")
        print("="*60)
        print("\n📌 Next Steps:")
        print("1. Go to QuickSight console: https://quicksight.aws.amazon.com/")
        print("2. Create analyses and dashboards using the datasets")
        print("3. Share dashboards with users (Warburg, JRAM, Tosei, GGhouse)")
        print("\n💡 Tip: Use the 'Create analysis' button in QuickSight UI")
        print("   and select the datasets created above.")
        
        return True


def main():
    parser = argparse.ArgumentParser(description='Set up QuickSight for Tokyo Beta BI')
    parser.add_argument('--aws-account-id', required=True, help='AWS Account ID')
    parser.add_argument('--region', default='ap-northeast-1', help='AWS Region')
    parser.add_argument('--profile', default='gghouse', help='AWS Profile')
    
    args = parser.parse_args()
    
    # Set AWS profile
    import os
    os.environ['AWS_PROFILE'] = args.profile
    
    # Run setup
    setup = QuickSightSetup(args.aws_account_id, args.region)
    success = setup.run_setup()
    
    exit(0 if success else 1)


if __name__ == '__main__':
    main()
