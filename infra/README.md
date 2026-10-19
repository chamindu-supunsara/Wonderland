# Cloud infrastructure

The Cognito authentication stack is deployed in Mumbai using [auth/cognito.yaml](auth/cognito.yaml); see [Step 02](../docs/steps/02-cognito-auth.md). Step 05 messaging is deployed through [events/sns-sqs.json](events/sns-sqs.json); see [Step 05](../docs/steps/05-events-sns-sqs.md). The isolated [Step 09 feasibility experiment](feasibility/README.md) was deployed, tested and completely cleaned up; follow its [complete walkthrough](../docs/steps/09-cloud-feasibility.md). Step 10A Terraform bootstrap/foundation configurations are implemented and locally validated; full application cloud deployment remains in progress. Docker Compose is local development only and does not satisfy the assignment's cloud Kubernetes requirement.

Planned Terraform roots: bootstrap, foundation, platform, edge, and frontend. Automate VPC, EKS, RDS, ECR, remaining IAM/secrets/logs, API Gateway/VPC Link/ALB integration, and Angular Amplify Hosting. Reference the existing Cognito and messaging stacks or deliberately import/migrate them; do not duplicate their resources. Use a sequenced workflow for controller-created ALB readiness and frontend configuration outputs. Verify AWS account permissions and a region-specific cost estimate before provisioning the remaining platform.


See [the Step 10 guide](../docs/steps/10-cloud-deployment.md). The bootstrap plan is state-storage only. The foundation, edge/frontend roots and Helm operational integration have separate exit checks; the starter chart alone is not a complete cloud application.
