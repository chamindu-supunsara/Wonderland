resource "aws_apigatewayv2_api" "public" {
  name          = "wonderland-demo-public"
  protocol_type = "HTTP"
  cors_configuration {
    allow_origins = ["https://main.${aws_amplify_app.frontend.default_domain}"]
    allow_methods = ["GET", "POST", "PUT", "OPTIONS"]
    allow_headers = ["authorization", "content-type", "idempotency-key"]
    max_age       = 300
  }
}
resource "aws_apigatewayv2_vpc_link" "private" {
  name               = "wonderland-demo-private"
  subnet_ids         = var.subnet_ids
  security_group_ids = [aws_security_group.link.id]
}
resource "aws_apigatewayv2_integration" "private" {
  api_id                 = aws_apigatewayv2_api.public.id
  integration_type       = "HTTP_PROXY"
  integration_method     = "ANY"
  integration_uri        = aws_lb_listener.private.arn
  connection_type        = "VPC_LINK"
  connection_id          = aws_apigatewayv2_vpc_link.private.id
  payload_format_version = "1.0"
  timeout_milliseconds   = 29000
  request_parameters     = { "overwrite:path" = "$request.path" }
}
resource "aws_apigatewayv2_authorizer" "cognito" {
  api_id           = aws_apigatewayv2_api.public.id
  authorizer_type  = "JWT"
  identity_sources = ["$request.header.Authorization"]
  name             = "WonderlandCognitoAccessTokens"
  jwt_configuration {
    audience = ["202ssal4mlube43ttm0j5m3k4i"]
    issuer   = "https://cognito-idp.ap-south-1.amazonaws.com/ap-south-1_aBuDlZ9RC"
  }
}
resource "aws_apigatewayv2_route" "application" {
  for_each             = local.routes
  api_id               = aws_apigatewayv2_api.public.id
  route_key            = each.key
  target               = "integrations/${aws_apigatewayv2_integration.private.id}"
  authorization_type   = each.value.public ? "NONE" : "JWT"
  authorizer_id        = each.value.public ? null : aws_apigatewayv2_authorizer.cognito.id
  authorization_scopes = each.value.public ? null : ["aws.cognito.signin.user.admin"]
}
resource "aws_cloudwatch_log_group" "gateway" {
  name              = "/aws/apigateway/wonderland-demo-public"
  retention_in_days = 7
}
resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.public.id
  name        = "$default"
  auto_deploy = true
  default_route_settings {
    throttling_burst_limit = 20
    throttling_rate_limit  = 5
  }
  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.gateway.arn
    format          = jsonencode({ requestId = "$context.requestId", routeKey = "$context.routeKey", status = "$context.status", latency = "$context.responseLatency", integrationError = "$context.integrationErrorMessage" })
  }
}
