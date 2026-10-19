variable "operator_arn" {
  type        = string
  description = "Permanent non-root IAM role/user ARN; resolve an SSO role with iam:GetRole."
  validation {
    condition     = can(regex("^arn:aws:iam::708919751353:(role|user)/.+$", var.operator_arn))
    error_message = "Use an IAM role/user in account 708919751353; never root or an STS session ARN."
  }
}
variable "operator_cidr" {
  type        = string
  description = "Current operator public IPv4 /32 for Kubernetes API access."
  validation {
    condition     = can(cidrnetmask(var.operator_cidr)) && try(tonumber(split("/", var.operator_cidr)[1]) == 32, false)
    error_message = "Only one IPv4 /32 is allowed; do not use 0.0.0.0/0."
  }
}
variable "kubernetes_version" {
  type    = string
  default = "1.35"
}
variable "node_count" {
  type        = number
  default     = 2
  description = "Two t3.medium workers consume four Standard On-Demand vCPUs; confirmed quota was five."
  validation {
    condition     = contains([1, 2], var.node_count)
    error_message = "This bounded demo permits one or two workers; review quota/cost before expanding."
  }
}
variable "database_class" {
  type    = string
  default = "db.t4g.small"
  validation {
    condition     = contains(["db.t4g.micro", "db.t4g.small"], var.database_class)
    error_message = "Use an explicitly reviewed small demo database."
  }
}
variable "database_deletion_protection" {
  type        = bool
  default     = true
  description = "Deliberately disable only for an approved teardown after backup review."
}
