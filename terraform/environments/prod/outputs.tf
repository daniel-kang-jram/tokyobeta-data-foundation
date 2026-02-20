# Production Environment Outputs

output "vpc_id" {
  description = "ID of the VPC"
  value       = module.networking.vpc_id
}

output "aurora_cluster_endpoint" {
  description = "Aurora cluster writer endpoint (public)"
  value       = module.aurora.public_cluster_endpoint
}

output "aurora_reader_endpoint" {
  description = "Aurora cluster reader endpoint"
  value       = module.aurora.reader_endpoint
}

output "aurora_database_name" {
  description = "Aurora database name"
  value       = module.aurora.database_name
}

output "glue_job_name" {
  description = "Name of the Glue ETL job"
  value       = module.glue.glue_job_name
}

output "glue_connection_name" {
  description = "Name of the Glue Aurora connection"
  value       = module.glue.glue_connection_name
}

output "eventbridge_rule" {
  description = "EventBridge rule schedule"
  value       = module.eventbridge.schedule_expression
}

output "sns_alert_topic_arn" {
  description = "SNS topic ARN for alerts"
  value       = module.monitoring.sns_topic_arn
}

output "deployment_instructions" {
  description = "Next steps for completing deployment"
  value       = <<-EOT
  
  ✅ Infrastructure deployed successfully!
  
  Next steps:
  
  1. Upload Glue script to S3:
     aws s3 cp glue/scripts/daily_etl.py s3://${var.s3_source_bucket}/glue-scripts/daily_etl.py --profile gghouse
  
  2. Upload dbt project to S3:
     aws s3 sync dbt/ s3://${var.s3_source_bucket}/dbt-project/ --profile gghouse
  
  3. Confirm SNS subscription email(s) (check inbox for "${var.alert_email}" and any addresses in alert_emails)
  
  4. Initialize database schemas:
     scripts/init_db.sh
  
  5. Test Glue job manually:
     aws glue start-job-run --job-name ${module.glue.glue_job_name} --profile gghouse
  
  6. Monitor job execution:
     aws glue get-job-run --job-name ${module.glue.glue_job_name} --run-id <run-id> --profile gghouse
  
  7. Verify analytics tables:
     mysql -h ${module.aurora.public_cluster_endpoint} -u admin -p tokyobeta -e "SHOW TABLES IN analytics"
  
  8. Set up QuickSight (see docs/QUICKSIGHT_SETUP.md)
  
  Evidence hosting (manual DNS):
  - CloudFront domain: ${module.evidence_hosting.cloudfront_domain_name}
  - ACM validation records: see output `evidence_acm_validation_records`
  
  Aurora endpoint: ${module.aurora.public_cluster_endpoint}
  Glue job: ${module.glue.glue_job_name}
  Daily trigger: ${module.eventbridge.schedule_expression}
  
  EOT
}

output "evidence_cloudfront_domain" {
  description = "CloudFront distribution domain for Evidence (CNAME target)"
  value       = module.evidence_hosting.cloudfront_domain_name
}

output "evidence_acm_validation_records" {
  description = "Add these CNAMEs in Sakura DNS to validate ACM certificate"
  value       = module.evidence_hosting.acm_validation_records
}

output "evidence_cognito_domain" {
  description = "Cognito hosted UI domain"
  value       = module.evidence_hosting.cognito_domain
}

output "evidence_snapshot_cloudfront_domain" {
  description = "CloudFront distribution domain for snapshot Evidence"
  value       = module.evidence_snapshot_hosting.cloudfront_domain_name
}

output "evidence_snapshot_acm_validation_records" {
  description = "DNS CNAME records to validate snapshot Evidence ACM certificate"
  value       = module.evidence_snapshot_hosting.acm_validation_records
}

output "evidence_snapshot_codebuild_project_name" {
  description = "CodeBuild project name for snapshot dashboard refresh"
  value       = module.evidence_snapshot_hosting.codebuild_project_name
}
