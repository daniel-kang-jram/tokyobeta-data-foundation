output "s3_bucket_name" {
  description = "S3 bucket hosting Evidence build"
  value       = aws_s3_bucket.site.bucket
}

output "cloudfront_domain_name" {
  description = "CloudFront distribution domain name (use as CNAME target in external DNS)"
  value       = aws_cloudfront_distribution.site.domain_name
}

output "acm_validation_records" {
  description = "DNS validation records to add in external DNS provider"
  value = [
    for dvo in aws_acm_certificate.site.domain_validation_options : {
      name  = dvo.resource_record_name
      type  = dvo.resource_record_type
      value = dvo.resource_record_value
    }
  ]
}

output "cognito_user_pool_id" {
  description = "Cognito User Pool ID (deprecated - not created when using Basic Auth)"
  value       = try(aws_cognito_user_pool.pool[0].id, null)
}

output "cognito_domain" {
  description = "Cognito hosted UI domain (deprecated - not created when using Basic Auth)"
  value       = try(aws_cognito_user_pool_domain.domain[0].domain, null)
}

output "codebuild_project_name" {
  description = "CodeBuild project name (daily refresh)"
  value       = try(aws_codebuild_project.refresh[0].name, null)
}
