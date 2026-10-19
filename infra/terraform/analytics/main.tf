terraform {
  required_version = ">= 1.16.0, < 2.0.0"
  required_providers { aws = { source = "hashicorp/aws", version = "~> 6.66.0" } }
  backend "s3" {}
}
provider "aws" {
  region              = "ap-south-1"
  allowed_account_ids = ["708919751353"]
  default_tags { tags = { Project = "Wonderland", Environment = "demo", ManagedBy = "Terraform" } }
}
resource "aws_secretsmanager_secret" "bi" {
  for_each                = toset(["metabase-app", "metabase-reporting"])
  name                    = "wonderland-demo/${each.key}"
  description             = "Private mock BI credentials; values generated only by the temporary in-cluster bootstrap"
  recovery_window_in_days = 7
  # Keep the encryption key and credentials for the agreed 14-day snapshot recovery review.
  lifecycle { prevent_destroy = true }
}
output "secret_arns" { value = { for k, v in aws_secretsmanager_secret.bi : k => v.arn } }
