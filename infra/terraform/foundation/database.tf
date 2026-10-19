resource "aws_security_group" "database" {
  name_prefix = "${local.name}-database-"
  vpc_id      = aws_vpc.main.id
}
resource "aws_vpc_security_group_ingress_rule" "database" {
  security_group_id            = aws_security_group.database.id
  referenced_security_group_id = aws_security_group.nodes.id
  ip_protocol                  = "tcp"
  from_port                    = 5432
  to_port                      = 5432
}
resource "aws_db_subnet_group" "main" {
  name       = local.name
  subnet_ids = aws_subnet.database[*].id
}
resource "aws_db_parameter_group" "main" {
  name_prefix = "${local.name}-"
  family      = "postgres16"
  parameter {
    name         = "rds.force_ssl"
    value        = "1"
    apply_method = "pending-reboot" # Matches AWS's returned method for this default-valued parameter.
  }
}
resource "random_id" "snapshot" { byte_length = 4 }
resource "aws_db_instance" "main" {
  identifier                      = local.name
  engine                          = "postgres"
  engine_version                  = "16"
  engine_lifecycle_support        = "open-source-rds-extended-support-disabled"
  instance_class                  = var.database_class
  allocated_storage               = 20
  max_allocated_storage           = 40
  storage_type                    = "gp3"
  storage_encrypted               = true
  db_name                         = "wonderland"
  username                        = "wonderland_admin"
  manage_master_user_password     = true
  db_subnet_group_name            = aws_db_subnet_group.main.name
  vpc_security_group_ids          = [aws_security_group.database.id]
  parameter_group_name            = aws_db_parameter_group.main.name
  publicly_accessible             = false
  multi_az                        = false
  backup_retention_period         = 7
  auto_minor_version_upgrade      = true
  deletion_protection             = var.database_deletion_protection
  skip_final_snapshot             = false
  final_snapshot_identifier       = "${local.name}-final-${random_id.snapshot.hex}"
  copy_tags_to_snapshot           = true
  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]
}
# Containers only. A privileged DB bootstrap writes credentials later, outside Terraform state.
resource "aws_secretsmanager_secret" "service" {
  for_each                = local.services
  name                    = "${local.name}/${each.key}"
  recovery_window_in_days = 7
}
