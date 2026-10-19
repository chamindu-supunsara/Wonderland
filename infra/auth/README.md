# Managed identity

`cognito.yaml` is the CloudFormation source of truth for Wonderland identity. Deployed as `wonderland-dev-auth` in Mumbai on 15 October 2026. See [Step 02](../../docs/steps/02-cognito-auth.md) for outputs, deployment, roles, limitations, testing and resource lifecycle.

This stack owns the Cognito pool, public Angular client and empty Administrators group. Other infrastructure roots must reference these resources instead of creating duplicates. User membership is assigned deliberately through privileged AWS access and is not managed by public signup.
