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
  
  3. Confirm SNS subscription email (check inbox for "${var.alert_email}")
  
  4. Initialize database schemas:
     scripts/init_db.sh
  
  5. Test Glue job manually:
     aws glue start-job-run --job-name ${module.glue.glue_job_name} --profile gghouse
  
  6. Monitor job execution:
     aws glue get-job-run --job-name ${module.glue.glue_job_name} --run-id <run-id> --profile gghouse
  
  7. Verify analytics tables:
     mysql -h ${module.aurora.public_cluster_endpoint} -u admin -p tokyobeta -e "SHOW TABLES IN analytics"
  
  8. Set up QuickSight (see docs/QUICKSIGHT_SETUP.md)
  
  Aurora endpoint: ${module.aurora.public_cluster_endpoint}
  Glue job: ${module.glue.glue_job_name}
  Daily trigger: ${module.eventbridge.schedule_expression}
  
  EOT
}
