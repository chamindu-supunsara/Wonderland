output "cluster_name" { value = aws_eks_cluster.main.name }
output "vpc_id" { value = aws_vpc.main.id }
output "private_compute_subnets" { value = aws_subnet.compute[*].id }
output "node_security_group_id" { value = aws_security_group.nodes.id }
output "repositories" { value = { for key, repository in aws_ecr_repository.service : key => repository.repository_url } }
output "database_host" { value = aws_db_instance.main.address }
output "database_master_secret_arn" { value = aws_db_instance.main.master_user_secret[0].secret_arn }
output "service_secret_arns" { value = { for key, secret in aws_secretsmanager_secret.service : key => secret.arn } }
output "cognito" {
  value = {
    region           = "ap-south-1"
    userPoolId       = data.aws_cloudformation_stack.identity.outputs["UserPoolId"]
    userPoolClientId = data.aws_cloudformation_stack.identity.outputs["UserPoolClientId"]
  }
}
