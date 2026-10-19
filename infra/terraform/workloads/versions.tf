terraform {
  required_version = ">= 1.16.0, < 2.0.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 6.66.0" }
  }
  backend "s3" {}
}
provider "aws" {
  region              = "ap-south-1"
  allowed_account_ids = ["708919751353"]
  default_tags {
    tags = { Project = "Wonderland", Environment = "demo", ManagedBy = "Terraform" }
  }
}
locals {
  prefix  = "wonderland-demo"
  account = "708919751353"
  region  = "ap-south-1"
  routes = {
    booking-prices       = "catalog"
    analytics-bookings   = "booking"
    analytics-admissions = "admission"
  }
  publishers = {
    catalog-publisher   = "catalog"
    booking-publisher   = "booking"
    admission-publisher = "admission"
  }
  identities = merge(local.publishers, local.routes)
}
data "aws_kms_key" "sns" { key_id = "alias/aws/sns" }
