terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"

      # CloudFront certificates must be created in us-east-1.
      configuration_aliases = [aws.us_east_1]
    }
  }
}

locals {
  name_prefix = "${var.project_name}-${var.environment}-evidence"

  tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "Terraform"
  }

  # Evidence app uses these fixed paths.
  callback_path = "/auth/callback"
  logout_path   = "/auth/logout"

  # Use CloudFront URL until custom domain/DNS is ready.
  auth_base_url = var.auth_base_url != null ? var.auth_base_url : "https://${var.custom_domain_name}"
}

# ----------------------------
# S3 + CloudFront (static hosting)
# ----------------------------

resource "aws_s3_bucket" "site" {
  bucket = "${local.name_prefix}-site"
}

resource "aws_s3_bucket_ownership_controls" "site" {
  bucket = aws_s3_bucket.site.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_public_access_block" "site" {
  bucket                  = aws_s3_bucket.site.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_cloudfront_origin_access_control" "oac" {
  name                              = "${local.name_prefix}-oac"
  description                       = "OAC for Evidence S3 origin"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

# ACM cert must be in us-east-1 for CloudFront.
# DNS validation will be completed manually in Sakura.
resource "aws_acm_certificate" "site" {
  provider          = aws.us_east_1
  domain_name       = var.custom_domain_name
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
  }
}

# ----------------------------
# CloudFront Function for HTTP Basic Auth
# ----------------------------

resource "aws_cloudfront_function" "basic_auth" {
  count   = var.enable_auth && length(var.auth_users) > 0 ? 1 : 0
  name    = "${local.name_prefix}-basic-auth"
  runtime = "cloudfront-js-2.0"
  comment = "HTTP Basic Auth for Evidence dashboard"
  publish = true
  code    = templatefile("${path.module}/src/basic_auth.js", {
    auth_users_json = jsonencode([
      for username, password in var.auth_users :
      base64encode("${username}:${password}")
    ])
  })
}

# ----------------------------
# Cognito (DEPRECATED - kept for reference, not used with Basic Auth)
# ----------------------------

# Cognito user pool (MFA required, TOTP)
resource "aws_cognito_user_pool" "pool" {
  count = 0 # Disabled - using CloudFront Functions Basic Auth instead
  name = "${local.name_prefix}-user-pool"

  # MFA is OPTIONAL to avoid redirect loops during initial setup
  # Users can enable MFA after first login through Cognito Hosted UI
  mfa_configuration = "OPTIONAL"

  software_token_mfa_configuration {
    enabled = true
  }

  password_policy {
    minimum_length                   = 12
    require_lowercase                = true
    require_numbers                  = true
    require_symbols                  = true
    require_uppercase                = true
    temporary_password_validity_days = 7
  }

  admin_create_user_config {
    allow_admin_create_user_only = true
  }
}

resource "aws_cognito_user_pool_domain" "domain" {
  count        = 0 # Disabled - using CloudFront Functions Basic Auth instead
  domain       = var.cognito_domain_prefix
  user_pool_id = aws_cognito_user_pool.pool[0].id
}

# Public client for hosted UI + PKCE.
resource "aws_cognito_user_pool_client" "client" {
  count        = 0 # Disabled - using CloudFront Functions Basic Auth instead
  name         = "${local.name_prefix}-app-client"
  user_pool_id = aws_cognito_user_pool.pool[0].id

  generate_secret = false

  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_flows                  = ["code"]
  allowed_oauth_scopes                 = ["openid", "email", "profile"]

  supported_identity_providers = ["COGNITO"]

  callback_urls = distinct([
    "${local.auth_base_url}${local.callback_path}",
    # Keep the eventual custom domain callback pre-registered.
    "https://${var.custom_domain_name}${local.callback_path}"
  ])

  logout_urls = distinct([
    # Used by /oauth2/logout (logout_uri param).
    "${local.auth_base_url}/",
    # Convenience endpoint that clears our cookies.
    "${local.auth_base_url}${local.logout_path}",
    # Keep the eventual custom domain sign-out URLs pre-registered.
    "https://${var.custom_domain_name}/",
    "https://${var.custom_domain_name}${local.logout_path}"
  ])

  explicit_auth_flows = [
    "ALLOW_USER_SRP_AUTH",
    "ALLOW_REFRESH_TOKEN_AUTH",
    "ALLOW_USER_PASSWORD_AUTH"
  ]
}

# Lambda@Edge auth gate (viewer request)
# Implemented in us-east-1 and associated with CloudFront.
resource "aws_iam_role" "edge_role" {
  count = 0 # Disabled - using CloudFront Functions Basic Auth instead
  name  = "${local.name_prefix}-edge-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Principal = {
          Service = [
            "lambda.amazonaws.com",
            "edgelambda.amazonaws.com"
          ]
        },
        Action = "sts:AssumeRole"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "edge_basic" {
  count      = 0 # Disabled - using CloudFront Functions Basic Auth instead
  role       = aws_iam_role.edge_role[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

data "aws_region" "current" {}

data "aws_iam_policy_document" "edge_logs" {
  statement {
    effect = "Allow"
    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents"
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "edge_logs" {
  count  = 0 # Disabled - using CloudFront Functions Basic Auth instead
  name   = "${local.name_prefix}-edge-logs"
  role   = aws_iam_role.edge_role[0].id
  policy = data.aws_iam_policy_document.edge_logs.json
}

# DEPRECATED: Lambda@Edge Cognito auth (replaced by CloudFront Functions Basic Auth)
# Keeping commented for reference
# 
# locals {
#   cognito_hosted_ui_base = "https://${aws_cognito_user_pool_domain.domain[0].domain}.auth.${data.aws_region.current.name}.amazoncognito.com"
# }
# 
# locals {
#   edge_js = templatefile("${path.module}/src/edge_auth.js.tmpl", {
#     cognito_domain  = aws_cognito_user_pool_domain.domain[0].domain
#     cognito_region  = data.aws_region.current.name
#     user_pool_id    = aws_cognito_user_pool.pool[0].id
#     client_id       = aws_cognito_user_pool_client.client[0].id
#     redirect_uri    = "${local.auth_base_url}${local.callback_path}"
#     logout_redirect = "${local.auth_base_url}/"
#   })
# }
# 
# data "archive_file" "edge_zip" {
#   type        = "zip"
#   output_path = "${path.module}/.build/edge_auth.zip"
# 
#   source {
#     content  = local.edge_js
#     filename = "index.js"
#   }
# }

resource "aws_lambda_function" "edge" {
  count    = 0 # Disabled - using CloudFront Functions Basic Auth instead
  provider = aws.us_east_1

  function_name = "${local.name_prefix}-edge-auth"
  role          = aws_iam_role.edge_role[0].arn
  handler       = "index.handler"
  runtime       = "nodejs18.x"

  filename         = "dummy.zip" # data.archive_file.edge_zip[0].output_path
  source_code_hash = "dummy"     # data.archive_file.edge_zip[0].output_base64sha256

  publish = true
}

# CloudFront distribution
resource "aws_cloudfront_distribution" "site" {
  enabled             = true
  is_ipv6_enabled     = true
  comment             = "Evidence static site (${var.environment})"
  default_root_object = "index.html"

  aliases = var.enable_custom_domain ? [var.custom_domain_name] : []

  origin {
    domain_name              = aws_s3_bucket.site.bucket_regional_domain_name
    origin_id                = "s3-origin"
    origin_access_control_id = aws_cloudfront_origin_access_control.oac.id
  }

  default_cache_behavior {
    allowed_methods  = ["GET", "HEAD", "OPTIONS"]
    cached_methods   = ["GET", "HEAD", "OPTIONS"]
    target_origin_id = "s3-origin"

    viewer_protocol_policy = "redirect-to-https"

    compress = true

    # HTTP Basic Auth via CloudFront Functions
    dynamic "function_association" {
      for_each = var.enable_auth && length(var.auth_users) > 0 ? [1] : []
      content {
        event_type   = "viewer-request"
        function_arn = aws_cloudfront_function.basic_auth[0].arn
      }
    }

    min_ttl     = 0
    default_ttl = 3600
    max_ttl     = 86400

    forwarded_values {
      query_string = true
      cookies {
        # Auth is enforced at viewer-request; don't vary cache by user cookies.
        forward = "none"
      }
    }
  }

  # Useful for SPA-style routing.
  custom_error_response {
    error_code            = 403
    response_code         = 200
    response_page_path    = "/index.html"
    error_caching_min_ttl = 0
  }

  custom_error_response {
    error_code            = 404
    response_code         = 200
    response_page_path    = "/index.html"
    error_caching_min_ttl = 0
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    acm_certificate_arn            = var.enable_custom_domain ? aws_acm_certificate.site.arn : null
    ssl_support_method             = var.enable_custom_domain ? "sni-only" : null
    minimum_protocol_version       = "TLSv1.2_2021"
    cloudfront_default_certificate = var.enable_custom_domain ? false : true
  }

  depends_on = [aws_acm_certificate.site]
}

# Allow CloudFront to read from S3.
data "aws_iam_policy_document" "site_policy" {
  statement {
    sid = "AllowCloudFrontRead"

    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.site.arn}/*"]

    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = [aws_cloudfront_distribution.site.arn]
    }
  }
}

resource "aws_s3_bucket_policy" "site" {
  bucket = aws_s3_bucket.site.id
  policy = data.aws_iam_policy_document.site_policy.json
}

# ----------------------------
# Scheduled refresh (CodeBuild) - optional until repo is wired
# ----------------------------

resource "aws_iam_role" "codebuild" {
  count = var.evidence_repo_connection_arn == null ? 0 : 1

  name = "${local.name_prefix}-codebuild-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Principal = {
          Service = "codebuild.amazonaws.com"
        },
        Action = "sts:AssumeRole"
      }
    ]
  })
}

resource "aws_iam_role_policy" "codebuild" {
  count = var.evidence_repo_connection_arn == null ? 0 : 1

  name = "${local.name_prefix}-codebuild-policy"
  role = aws_iam_role.codebuild[0].id

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Action = [
          "secretsmanager:GetSecretValue"
        ],
        Resource = "*"
      },
      {
        Effect = "Allow",
        Action = [
          "codestar-connections:UseConnection"
        ],
        Resource = var.evidence_repo_connection_arn
      },
      {
        Effect = "Allow",
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ],
        Resource = "*"
      },
      {
        Effect = "Allow",
        Action = [
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ],
        Resource = [
          aws_s3_bucket.site.arn,
          "${aws_s3_bucket.site.arn}/*"
        ]
      },
      {
        Effect = "Allow",
        Action = [
          "s3:GetObject",
          "s3:GetObjectVersion",
          "s3:GetBucketLocation",
          "s3:ListBucket"
        ],
        Resource = [
          aws_s3_bucket.pipeline_artifacts[0].arn,
          "${aws_s3_bucket.pipeline_artifacts[0].arn}/*"
        ]
      },
      {
        Effect = "Allow",
        Action = [
          "cloudfront:CreateInvalidation"
        ],
        Resource = "*"
      },
      {
        Effect = "Allow",
        Action = [
          "ec2:CreateNetworkInterface",
          "ec2:CreateNetworkInterfacePermission",
          "ec2:DescribeNetworkInterfaces",
          "ec2:DeleteNetworkInterface",
          "ec2:DescribeSubnets",
          "ec2:DescribeSecurityGroups",
          "ec2:DescribeVpcs",
          "ec2:DescribeRouteTables",
          "ec2:DescribeDhcpOptions",
          "ec2:DescribeAvailabilityZones"
        ],
        Resource = "*"
      }
    ]
  })
}

resource "aws_codebuild_project" "refresh" {
  count = var.evidence_repo_connection_arn == null ? 0 : 1

  name         = "${local.name_prefix}-refresh"
  service_role = aws_iam_role.codebuild[0].arn

  artifacts {
    type = "CODEPIPELINE"
  }

  environment {
    compute_type                = "BUILD_GENERAL1_MEDIUM"
    image                       = "aws/codebuild/standard:7.0"
    type                        = "LINUX_CONTAINER"
    image_pull_credentials_type = "CODEBUILD"

    environment_variable {
      name  = "EVIDENCE_SECRET_ID"
      value = var.aurora_evidence_secret_id
    }

    environment_variable {
      name  = "EVIDENCE_S3_BUCKET"
      value = aws_s3_bucket.site.bucket
    }

    environment_variable {
      name  = "EVIDENCE_CF_DISTRIBUTION_ID"
      value = aws_cloudfront_distribution.site.id
    }
  }

  source {
    # Source is provided by CodePipeline (which uses CodeStar Connections).
    type      = "CODEPIPELINE"
    buildspec = "evidence/buildspec.yml"
  }

  vpc_config {
    vpc_id             = var.vpc_id
    subnets            = var.private_subnet_ids
    security_group_ids = [var.codebuild_security_group_id]
  }
}

# ----------------------------
# CodePipeline (Source via CodeStar Connections)
# ----------------------------

resource "aws_s3_bucket" "pipeline_artifacts" {
  count = var.evidence_repo_connection_arn == null ? 0 : 1

  bucket = "${local.name_prefix}-evidence-pipeline"

  tags = local.tags
}

resource "aws_s3_bucket_public_access_block" "pipeline_artifacts" {
  count = var.evidence_repo_connection_arn == null ? 0 : 1

  bucket                  = aws_s3_bucket.pipeline_artifacts[0].id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "pipeline_artifacts" {
  count = var.evidence_repo_connection_arn == null ? 0 : 1

  bucket = aws_s3_bucket.pipeline_artifacts[0].id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_iam_role" "codepipeline" {
  count = var.evidence_repo_connection_arn == null ? 0 : 1

  name = "${local.name_prefix}-codepipeline-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Principal = {
          Service = "codepipeline.amazonaws.com"
        },
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = local.tags
}

resource "aws_iam_role_policy" "codepipeline" {
  count = var.evidence_repo_connection_arn == null ? 0 : 1

  name = "${local.name_prefix}-codepipeline-policy"
  role = aws_iam_role.codepipeline[0].id

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Action = [
          "codestar-connections:UseConnection"
        ],
        Resource = var.evidence_repo_connection_arn
      },
      {
        Effect = "Allow",
        Action = [
          "s3:GetObject",
          "s3:GetObjectVersion",
          "s3:PutObject",
          "s3:ListBucket"
        ],
        Resource = [
          aws_s3_bucket.pipeline_artifacts[0].arn,
          "${aws_s3_bucket.pipeline_artifacts[0].arn}/*"
        ]
      },
      {
        Effect = "Allow",
        Action = [
          "codebuild:StartBuild",
          "codebuild:BatchGetBuilds"
        ],
        Resource = aws_codebuild_project.refresh[0].arn
      }
    ]
  })
}

resource "aws_codepipeline" "refresh" {
  count = var.evidence_repo_connection_arn == null ? 0 : 1

  name     = "${local.name_prefix}-evidence-refresh"
  role_arn = aws_iam_role.codepipeline[0].arn

  artifact_store {
    location = aws_s3_bucket.pipeline_artifacts[0].bucket
    type     = "S3"
  }

  stage {
    name = "Source"

    action {
      name             = "Source"
      category         = "Source"
      owner            = "AWS"
      provider         = "CodeStarSourceConnection"
      version          = "1"
      output_artifacts = ["SourceOutput"]

      configuration = {
        ConnectionArn    = var.evidence_repo_connection_arn
        FullRepositoryId = var.evidence_repo_full_name
        BranchName       = var.evidence_repo_branch
        DetectChanges    = "false"
      }
    }
  }

  stage {
    name = "Build"

    action {
      name            = "Build"
      category        = "Build"
      owner           = "AWS"
      provider        = "CodeBuild"
      version         = "1"
      input_artifacts = ["SourceOutput"]

      configuration = {
        ProjectName = aws_codebuild_project.refresh[0].name
      }
    }
  }

  tags = local.tags
}

resource "aws_cloudwatch_event_rule" "schedule" {
  count = var.evidence_repo_connection_arn == null ? 0 : 1

  name                = "${local.name_prefix}-daily-refresh"
  description         = "Daily Evidence sources/build refresh"
  schedule_expression = var.schedule_expression
}

resource "aws_iam_role" "events" {
  count = var.evidence_repo_connection_arn == null ? 0 : 1

  name = "${local.name_prefix}-events-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Principal = {
          Service = "events.amazonaws.com"
        },
        Action = "sts:AssumeRole"
      }
    ]
  })
}

resource "aws_iam_role_policy" "events_invoke_codebuild" {
  count = var.evidence_repo_connection_arn == null ? 0 : 1

  name = "${local.name_prefix}-events-invoke-codebuild"
  role = aws_iam_role.events[0].id

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Action = [
          "codepipeline:StartPipelineExecution"
        ],
        Resource = aws_codepipeline.refresh[0].arn
      }
    ]
  })
}

resource "aws_cloudwatch_event_target" "schedule" {
  count = var.evidence_repo_connection_arn == null ? 0 : 1

  rule      = aws_cloudwatch_event_rule.schedule[0].name
  target_id = "codepipeline"
  arn       = aws_codepipeline.refresh[0].arn

  role_arn = aws_iam_role.events[0].arn
}
