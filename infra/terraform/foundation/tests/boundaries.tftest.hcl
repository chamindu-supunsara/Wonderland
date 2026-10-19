mock_provider "aws" {
  mock_data "aws_caller_identity" { defaults = { account_id = "708919751353" } }
  mock_data "aws_availability_zones" { defaults = { names = ["ap-south-1a", "ap-south-1b"] } }
  mock_data "aws_cloudformation_stack" {
    defaults = { outputs = { UserPoolId = "ap-south-1_aBuDlZ9RC", UserPoolClientId = "202ssal4mlube43ttm0j5m3k4i" } }
  }
  mock_data "aws_eks_cluster_versions" {
    defaults = { cluster_versions = [{ cluster_version = "1.35", version_status = "STANDARD_SUPPORT" }] }
  }
  mock_data "aws_eks_addon_version" { defaults = { version = "v1.3.0-eksbuild.1" } }
}
mock_provider "random" {}
variables {
  operator_arn  = "arn:aws:iam::708919751353:role/TestOperator"
  operator_cidr = "203.0.113.10/32"
}
run "private_and_bounded" {
  command = plan
  assert {
    condition     = !aws_db_instance.main.publicly_accessible && aws_db_instance.main.storage_encrypted && aws_db_instance.main.manage_master_user_password && aws_db_instance.main.deletion_protection && !aws_db_instance.main.skip_final_snapshot
    error_message = "RDS must be private, encrypted, use a managed secret and retain deletion/backup safeguards."
  }
  assert {
    condition     = alltrue([for subnet in aws_subnet.compute : !subnet.map_public_ip_on_launch]) && length(aws_subnet.database) == 2 && length(aws_subnet.compute) == 2
    error_message = "Compute and database subnets must remain private across two AZs."
  }
  assert {
    condition     = aws_eks_cluster.main.access_config[0].bootstrap_cluster_creator_admin_permissions == false && aws_eks_cluster.main.upgrade_policy[0].support_type == "STANDARD" && aws_eks_node_group.main.scaling_config[0].max_size == 2
    error_message = "Disable implicit creator access, extended support and unbounded node scaling."
  }
  assert {
    condition     = length(aws_ecr_repository.service) == 5 && alltrue([for repository in aws_ecr_repository.service : repository.image_tag_mutability == "IMMUTABLE" && !repository.force_delete])
    error_message = "Five service repositories must use immutable tags and explicit image cleanup."
  }
  assert {
    condition     = length(aws_secretsmanager_secret.service) == 5 && contains([for parameter in aws_db_parameter_group.main.parameter : "${parameter.name}=${parameter.value}"], "rds.force_ssl=1")
    error_message = "Require five service secret containers and TLS for database clients."
  }
}
run "reject_root" {
  command = plan
  variables { operator_arn = "arn:aws:iam::708919751353:root" }
  expect_failures = [var.operator_arn]
}
run "reject_open_kubernetes_api" {
  command = plan
  variables { operator_cidr = "0.0.0.0/0" }
  expect_failures = [var.operator_cidr]
}
run "reject_unreviewed_capacity" {
  command = plan
  variables { node_count = 3 }
  expect_failures = [var.node_count]
}
run "reject_unsupported_cluster_version" {
  command = plan
  variables { kubernetes_version = "1.99" }
  expect_failures = [aws_eks_cluster.main]
}
