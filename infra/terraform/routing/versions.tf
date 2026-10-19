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
variable "vpc_id" { type = string }
variable "subnet_ids" { type = list(string) }
variable "node_security_group_id" { type = string }
variable "control_security_group_id" { type = string }
locals {
  prefix   = "wonderland-demo"
  services = toset(["catalog", "booking", "payment", "admission"])
  routes   = jsondecode(file("${path.module}/routes.json"))
}
