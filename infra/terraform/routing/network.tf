resource "aws_security_group" "link" {
  name        = "wonderland-demo-vpc-link"
  description = "API Gateway private link to the one internal ALB"
  vpc_id      = var.vpc_id
}
resource "aws_security_group" "alb" {
  name        = "wonderland-demo-edge"
  description = "Private ALB; ingress only from API Gateway VPC link"
  vpc_id      = var.vpc_id
}
resource "aws_vpc_security_group_egress_rule" "link_to_alb" {
  security_group_id            = aws_security_group.link.id
  referenced_security_group_id = aws_security_group.alb.id
  ip_protocol                  = "tcp"
  from_port                    = 80
  to_port                      = 80
}
resource "aws_vpc_security_group_ingress_rule" "link_to_alb" {
  security_group_id            = aws_security_group.alb.id
  referenced_security_group_id = aws_security_group.link.id
  ip_protocol                  = "tcp"
  from_port                    = 80
  to_port                      = 80
}
resource "aws_vpc_security_group_egress_rule" "alb_to_pods" {
  security_group_id            = aws_security_group.alb.id
  referenced_security_group_id = var.node_security_group_id
  ip_protocol                  = "tcp"
  from_port                    = 8000
  to_port                      = 8000
}
resource "aws_vpc_security_group_ingress_rule" "alb_to_pods" {
  security_group_id            = var.node_security_group_id
  referenced_security_group_id = aws_security_group.alb.id
  ip_protocol                  = "tcp"
  from_port                    = 8000
  to_port                      = 8000
}
resource "aws_vpc_security_group_ingress_rule" "controller_webhook" {
  security_group_id            = var.node_security_group_id
  referenced_security_group_id = var.control_security_group_id
  ip_protocol                  = "tcp"
  from_port                    = 9443
  to_port                      = 9443
}
resource "aws_lb" "edge" {
  name                       = "wonderland-demo-edge"
  internal                   = true
  load_balancer_type         = "application"
  security_groups            = [aws_security_group.alb.id]
  subnets                    = var.subnet_ids
  idle_timeout               = 30
  drop_invalid_header_fields = true
  # AWS documents HTTP API private requests as incompatible with strictest.
  # Defensive keeps desync mitigation enabled while allowing this integration.
  desync_mitigation_mode = "defensive"
}
resource "aws_lb_target_group" "api" {
  for_each             = local.services
  name                 = "wl-demo-${each.key}"
  port                 = 8000
  protocol             = "HTTP"
  target_type          = "ip"
  vpc_id               = var.vpc_id
  deregistration_delay = 30
  health_check {
    path                = "/health/ready"
    protocol            = "HTTP"
    matcher             = "200"
    interval            = 15
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 2
  }
}
resource "aws_lb_listener" "private" {
  load_balancer_arn = aws_lb.edge.arn
  port              = 80
  protocol          = "HTTP"
  default_action {
    type = "fixed-response"
    fixed_response {
      content_type = "application/json"
      message_body = "{\"detail\":\"Not found\"}"
      status_code  = "404"
    }
  }
}
resource "aws_lb_listener_rule" "booking" {
  listener_arn = aws_lb_listener.private.arn
  priority     = 10
  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api["booking"].arn
  }
  condition {
    path_pattern { regex_values = ["^/api/v1/(bookings(/.*)?|visit-slots|booking-policy|admin/visit-slots)$"] }
  }
}
resource "aws_lb_listener_rule" "payment" {
  listener_arn = aws_lb_listener.private.arn
  priority     = 20
  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api["payment"].arn
  }
  condition {
    path_pattern { values = ["/api/v1/payments/*"] }
  }
}
resource "aws_lb_listener_rule" "admission" {
  listener_arn = aws_lb_listener.private.arn
  priority     = 30
  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api["admission"].arn
  }
  condition {
    path_pattern { values = ["/api/v1/admissions/*"] }
  }
}
resource "aws_lb_listener_rule" "catalog" {
  listener_arn = aws_lb_listener.private.arn
  priority     = 40
  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api["catalog"].arn
  }
  condition {
    path_pattern { regex_values = ["^/api/v1/(attractions(/.*)?|ticket-tiers|users/me|admin/.*)$"] }
  }
}
