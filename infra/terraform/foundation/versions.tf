terraform {
  required_version = ">= 1.16.0, < 2.0.0"
  required_providers {
    aws    = { source = "hashicorp/aws", version = "~> 6.66.0" }
    random = { source = "hashicorp/random", version = "~> 3.7.0" }
  }
  # Use -backend=false for local validation. Create the bootstrap bucket before init.
  backend "s3" {}
}

provider "aws" {
  region              = "ap-south-1"
  allowed_account_ids = ["708919751353"]
  default_tags {
    tags = { Project = "Wonderland", Environment = "demo", ManagedBy = "Terraform" }
  }
}
data "aws_caller_identity" "current" {}
data "aws_availability_zones" "available" { state = "available" }
data "aws_cloudformation_stack" "identity" { name = "wonderland-dev-auth" }
data "aws_eks_cluster_versions" "standard" { version_status = "STANDARD_SUPPORT" }
locals {
  name     = "wonderland-demo"
  azs      = slice(data.aws_availability_zones.available.names, 0, 2)
  services = toset(["catalog", "booking", "payment", "admission", "analytics"])
}
