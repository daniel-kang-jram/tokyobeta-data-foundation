#!/usr/bin/env python3
"""
QuickSight Dashboard Deployment Script
Automates deployment of dashboards from JSON templates

Usage:
    python deploy_dashboards.py --environment prod --dashboard-dir ../../quicksight/dashboards
    python deploy_dashboards.py --export --dashboard-id <id> --output-dir ../../quicksight/dashboards
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List
import boto3
from botocore.exceptions import ClientError

class QuickSightDeployer:
    """Manages QuickSight dashboard deployments"""
    
    def __init__(self, region: str = 'ap-northeast-1'):
        self.quicksight = boto3.client('quicksight', region_name=region)
        self.sts = boto3.client('sts')
        self.account_id = self.sts.get_caller_identity()['Account']
        
    def export_dashboard(self, dashboard_id: str, output_dir: Path) -> Path:
        """
        Export existing dashboard definition to JSON
        
        Args:
            dashboard_id: QuickSight dashboard ID
            output_dir: Directory to save JSON template
            
        Returns:
            Path to exported JSON file
        """
        print(f"Exporting dashboard: {dashboard_id}")
        
        try:
            # Get dashboard definition
            response = self.quicksight.describe_dashboard(
                AwsAccountId=self.account_id,
                DashboardId=dashboard_id
            )
            
            dashboard = response['Dashboard']
            dashboard_name = dashboard['Name']
            
            # Get dashboard version
            version_response = self.quicksight.describe_dashboard_definition(
                AwsAccountId=self.account_id,
                DashboardId=dashboard_id,
                VersionNumber=dashboard['Version']['VersionNumber']
            )
            
            # Construct template
            template = {
                'dashboard_id': dashboard_id,
                'name': dashboard_name,
                'description': dashboard.get('Description', ''),
                'definition': version_response['Definition'],
                'permissions': self._get_dashboard_permissions(dashboard_id),
                'tags': dashboard.get('Tags', {})
            }
            
            # Save to file
            output_path = output_dir / f"{dashboard_id}.json"
            output_dir.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'w') as f:
                json.dump(template, f, indent=2, default=str)
            
            print(f"✅ Exported to: {output_path}")
            return output_path
            
        except ClientError as e:
            print(f"❌ Export failed: {e}")
            raise
    
    def _get_dashboard_permissions(self, dashboard_id: str) -> List[Dict]:
        """Get dashboard permissions"""
        try:
            response = self.quicksight.describe_dashboard_permissions(
                AwsAccountId=self.account_id,
                DashboardId=dashboard_id
            )
            return response.get('Permissions', [])
        except ClientError:
            return []
    
    def deploy_dashboard(self, template_path: Path, environment: str) -> str:
        """
        Deploy dashboard from JSON template
        
        Args:
            template_path: Path to JSON template file
            environment: Environment name (dev/prod)
            
        Returns:
            Dashboard ID
        """
        print(f"Deploying dashboard from: {template_path}")
        
        with open(template_path) as f:
            template = json.load(f)
        
        dashboard_id = f"{environment}-{template['dashboard_id']}"
        dashboard_name = f"{template['name']} ({environment.upper()})"
        
        try:
            # Check if dashboard exists
            try:
                self.quicksight.describe_dashboard(
                    AwsAccountId=self.account_id,
                    DashboardId=dashboard_id
                )
                dashboard_exists = True
                print(f"Dashboard exists, will update: {dashboard_id}")
            except ClientError as e:
                if e.response['Error']['Code'] == 'ResourceNotFoundException':
                    dashboard_exists = False
                    print(f"Creating new dashboard: {dashboard_id}")
                else:
                    raise
            
            # Prepare dashboard definition
            definition = template['definition']
            
            if dashboard_exists:
                # Update existing dashboard
                response = self.quicksight.update_dashboard(
                    AwsAccountId=self.account_id,
                    DashboardId=dashboard_id,
                    Name=dashboard_name,
                    Definition=definition,
                    VersionDescription=f"Deployed via script at {self._get_timestamp()}"
                )
            else:
                # Create new dashboard
                response = self.quicksight.create_dashboard(
                    AwsAccountId=self.account_id,
                    DashboardId=dashboard_id,
                    Name=dashboard_name,
                    Definition=definition,
                    Permissions=self._adapt_permissions(template.get('permissions', []), environment),
                    Tags=self._adapt_tags(template.get('tags', {}), environment)
                )
            
            # Publish dashboard
            self.quicksight.update_dashboard_published_version(
                AwsAccountId=self.account_id,
                DashboardId=dashboard_id,
                VersionNumber=response['VersionArn'].split('/')[-1]
            )
            
            print(f"✅ Dashboard deployed: {dashboard_id}")
            print(f"   ARN: {response['Arn']}")
            
            return dashboard_id
            
        except ClientError as e:
            print(f"❌ Deployment failed: {e}")
            raise
    
    def _adapt_permissions(self, permissions: List[Dict], environment: str) -> List[Dict]:
        """
        Adapt permissions for target environment
        Replace account-specific ARNs if needed
        """
        # Default read-only permissions for viewers
        return [
            {
                'Principal': f'arn:aws:quicksight:ap-northeast-1:{self.account_id}:user/default/viewer',
                'Actions': [
                    'quicksight:DescribeDashboard',
                    'quicksight:ListDashboardVersions',
                    'quicksight:QueryDashboard'
                ]
            }
        ]
    
    def _adapt_tags(self, tags: Dict, environment: str) -> List[Dict]:
        """Convert tags dict to QuickSight tag format"""
        tag_list = [
            {'Key': 'Environment', 'Value': environment},
            {'Key': 'ManagedBy', 'Value': 'Terraform'},
            {'Key': 'Project', 'Value': 'TokyoBeta-DataConsolidation'}
        ]
        
        for key, value in tags.items():
            if key not in ['Environment', 'ManagedBy', 'Project']:
                tag_list.append({'Key': key, 'Value': str(value)})
        
        return tag_list
    
    def _get_timestamp(self) -> str:
        """Get current timestamp string"""
        from datetime import datetime
        return datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
    
    def list_dashboards(self) -> List[Dict]:
        """List all dashboards in account"""
        try:
            response = self.quicksight.list_dashboards(
                AwsAccountId=self.account_id,
                MaxResults=100
            )
            return response.get('DashboardSummaryList', [])
        except ClientError as e:
            print(f"❌ Failed to list dashboards: {e}")
            return []


def main():
    parser = argparse.ArgumentParser(description='Deploy QuickSight dashboards')
    parser.add_argument('--environment', choices=['dev', 'prod'], default='prod',
                      help='Target environment')
    parser.add_argument('--region', default='ap-northeast-1',
                      help='AWS region')
    
    # Export mode
    parser.add_argument('--export', action='store_true',
                      help='Export existing dashboard to JSON')
    parser.add_argument('--dashboard-id',
                      help='Dashboard ID to export')
    parser.add_argument('--export-all', action='store_true',
                      help='Export all dashboards')
    
    # Deploy mode
    parser.add_argument('--dashboard-dir', type=Path,
                      default=Path(__file__).parent.parent.parent / 'quicksight' / 'dashboards',
                      help='Directory containing dashboard JSON templates')
    parser.add_argument('--dashboard-file',
                      help='Specific dashboard JSON file to deploy')
    
    # Output
    parser.add_argument('--output-dir', type=Path,
                      help='Output directory for exports (default: dashboard-dir)')
    
    args = parser.parse_args()
    
    deployer = QuickSightDeployer(region=args.region)
    
    try:
        if args.export or args.export_all:
            # Export mode
            output_dir = args.output_dir or args.dashboard_dir
            
            if args.export_all:
                print("Exporting all dashboards...")
                dashboards = deployer.list_dashboards()
                for dashboard in dashboards:
                    deployer.export_dashboard(dashboard['DashboardId'], output_dir)
            elif args.dashboard_id:
                deployer.export_dashboard(args.dashboard_id, output_dir)
            else:
                print("❌ Error: --dashboard-id required for export")
                sys.exit(1)
        
        else:
            # Deploy mode
            if args.dashboard_file:
                # Deploy single dashboard
                template_path = Path(args.dashboard_file)
                deployer.deploy_dashboard(template_path, args.environment)
            else:
                # Deploy all dashboards in directory
                dashboard_files = list(args.dashboard_dir.glob('*.json'))
                
                if not dashboard_files:
                    print(f"❌ No dashboard templates found in: {args.dashboard_dir}")
                    sys.exit(1)
                
                print(f"Found {len(dashboard_files)} dashboard templates")
                
                for template_path in dashboard_files:
                    try:
                        deployer.deploy_dashboard(template_path, args.environment)
                    except Exception as e:
                        print(f"⚠️  Failed to deploy {template_path.name}: {e}")
                        continue
        
        print("\n✅ Operation completed successfully")
        
    except Exception as e:
        print(f"\n❌ Operation failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
