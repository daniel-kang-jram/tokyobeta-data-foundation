# Glue Module Outputs

output "glue_job_name" {
  description = "Name of the Glue ETL job"
  value       = aws_glue_job.daily_etl.name
}

output "glue_job_arn" {
  description = "ARN of the Glue ETL job"
  value       = aws_glue_job.daily_etl.arn
}

output "glue_role_arn" {
  description = "ARN of the Glue service role"
  value       = aws_iam_role.glue_service_role.arn
}

output "glue_connection_name" {
  description = "Name of the Glue connection to Aurora"
  value       = aws_glue_connection.aurora.name
}

output "catalog_database_source" {
  description = "Name of the Glue catalog source database"
  value       = aws_glue_catalog_database.source.name
}

output "catalog_database_staging" {
  description = "Name of the Glue catalog staging database"
  value       = aws_glue_catalog_database.staging.name
}

output "crawler_name" {
  description = "Name of the S3 dumps crawler"
  value       = aws_glue_crawler.s3_dumps.name
}

# New resilient ETL job outputs
output "staging_loader_name" {
  description = "Name of the staging loader Glue job"
  value       = aws_glue_job.staging_loader.name
}

output "staging_loader_arn" {
  description = "ARN of the staging loader Glue job"
  value       = aws_glue_job.staging_loader.arn
}

output "silver_transformer_name" {
  description = "Name of the silver transformer Glue job"
  value       = aws_glue_job.silver_transformer.name
}

output "silver_transformer_arn" {
  description = "ARN of the silver transformer Glue job"
  value       = aws_glue_job.silver_transformer.arn
}

output "gold_transformer_name" {
  description = "Name of the gold transformer Glue job"
  value       = aws_glue_job.gold_transformer.name
}

output "gold_transformer_arn" {
  description = "ARN of the gold transformer Glue job"
  value       = aws_glue_job.gold_transformer.arn
}

output "data_quality_test_name" {
  description = "Name of the data quality test Glue job"
  value       = aws_glue_job.data_quality_test.name
}

output "data_quality_test_arn" {
  description = "ARN of the data quality test Glue job"
  value       = aws_glue_job.data_quality_test.arn
}
