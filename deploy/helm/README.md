# Wonderland Helm starter

`wonderland/` renders four internal Python APIs and six independently enabled worker Deployments, ServiceAccounts, ClusterIP Services, API disruption budgets and non-secret runtime configuration. Immutable image digests and an exact HTTPS frontend origin are required when enabled. Checkout/admission stay MOCK.

Default `enabled: false` produces no workloads. `tests/render-values.yaml` is deliberately un-runnable test data. Run `scripts/check-deployment.ps1` from the repository root for provider-mocked Terraform checks and chart lint/render tests against EKS 1.35.

This starter does not create schemas, migrations, secrets, AWS workload roles/associations, ingress, API Gateway, Amplify or Metabase. Do not install it before completing those prerequisites. Follow [Step 10](../../docs/steps/10-cloud-deployment.md) for the staged deployment and honest status.
