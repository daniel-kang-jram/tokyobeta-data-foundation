# EC2 Management Module
# Manages existing EC2 instance for cron jobs and attaches IAM role

# Data source to reference existing EC2 instance
data "aws_instance" "existing_cron_instance" {
  instance_id = var.existing_instance_id
}

# Attach IAM instance profile to existing EC2 instance
# Note: This requires the instance to be stopped and started
resource "aws_ec2_instance_state" "cron_instance" {
  count       = var.manage_instance_state ? 1 : 0
  instance_id = var.existing_instance_id
  state       = var.desired_state
}

# Update instance IAM profile
# WARNING: Applying this will replace the instance profile
# The instance must be restarted for the new profile to take effect
resource "null_resource" "attach_instance_profile" {
  count = var.attach_iam_profile ? 1 : 0

  triggers = {
    instance_id      = var.existing_instance_id
    profile_name     = var.instance_profile_name
    instance_version = data.aws_instance.existing_cron_instance.instance_state
  }

  provisioner "local-exec" {
    command = <<-EOT
      # Associate IAM instance profile with EC2 instance
      aws ec2 associate-iam-instance-profile \
        --instance-id ${var.existing_instance_id} \
        --iam-instance-profile Name=${var.instance_profile_name} \
        --region ${var.aws_region} || true
    EOT
  }
}

# Tag the existing instance for better organization
resource "null_resource" "tag_instance" {
  count = var.update_tags ? 1 : 0

  triggers = {
    instance_id = var.existing_instance_id
    tags        = jsonencode(var.instance_tags)
  }

  provisioner "local-exec" {
    command = <<-EOT
      aws ec2 create-tags \
        --resources ${var.existing_instance_id} \
        --tags ${join(" ", [for k, v in var.instance_tags : "Key=${k},Value=${v}"])} \
        --region ${var.aws_region}
    EOT
  }
}
