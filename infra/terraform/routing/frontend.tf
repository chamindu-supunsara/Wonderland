locals {
  frontend_headers = <<-YAML
    customHeaders:
      - pattern: '**'
        headers:
          - key: Strict-Transport-Security
            value: max-age=31536000; includeSubDomains
          - key: X-Content-Type-Options
            value: nosniff
          - key: Referrer-Policy
            value: strict-origin-when-cross-origin
          - key: Content-Security-Policy
            value: "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self' data:; connect-src 'self' https://*.execute-api.ap-south-1.amazonaws.com https://cognito-idp.ap-south-1.amazonaws.com; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
      - pattern: /app-config.json
        headers:
          - key: Cache-Control
            value: no-store
    YAML
}
resource "aws_amplify_app" "frontend" {
  name                     = "wonderland-demo-frontend"
  platform                 = "WEB"
  enable_branch_auto_build = false
  custom_rule {
    source = "</^[^.]+$|\\.(?!(css|gif|ico|jpg|js|png|txt|svg|woff|woff2|ttf|map|json|webp)$)([^.]+$)/>"
    target = "/index.html"
    status = "200"
  }
  custom_headers = local.frontend_headers
  lifecycle {
    # Amplify returns an array although UpdateApp requires a customHeaders object.
    # Ignore serialization only; the postcondition still fails on changed headers.
    ignore_changes = [custom_headers]
    postcondition {
      condition     = try(jsondecode(self.custom_headers), yamldecode(self.custom_headers).customHeaders) == yamldecode(local.frontend_headers).customHeaders
      error_message = "Live Amplify security headers differ from the reviewed configuration."
    }
  }
}
resource "aws_amplify_branch" "main" {
  app_id            = aws_amplify_app.frontend.id
  branch_name       = "main"
  framework         = "Angular"
  stage             = "DEVELOPMENT"
  enable_auto_build = false
}
output "api_endpoint" { value = aws_apigatewayv2_api.public.api_endpoint }
output "frontend_origin" { value = "https://${aws_amplify_branch.main.branch_name}.${aws_amplify_app.frontend.default_domain}" }
output "amplify_app_id" { value = aws_amplify_app.frontend.id }
output "target_groups" { value = { for k, t in aws_lb_target_group.api : k => t.arn } }
output "alb_arn" { value = aws_lb.edge.arn }
output "vpc_link_id" { value = aws_apigatewayv2_vpc_link.private.id }
output "api_id" { value = aws_apigatewayv2_api.public.id }
