# Step 10D — API Gateway routing and Angular hosting

Status: **deployed and verified**. All 57 resources are deployed, Angular is published, 23 public checks and 22 live routing checks passed, and the real administrator/visitor walkthrough passed. Checkout, admission and analytics remain mock. This guide records every deployment stage, verification boundary and cleanup dependency.

## 1. Architecture and costs

Angular is built locally and published to Amplify's AWS-provided HTTPS domain. Its public `app-config.json` contains only the Gateway URL and existing Cognito pool/client IDs. The source development configuration remains unchanged. Git-linked delivery belongs to Step 11.

API Gateway HTTP API exposes **29 exact method/path routes**: three public catalog reads and 26 JWT-protected routes. It forwards through a private VPC link to **one internal ALB**, which routes to four existing service Deployments. The pinned AWS Load Balancer Controller **3.6.0** manages Pod IP registration through four TargetGroupBindings, so API rollouts do not require manually registering IPs. Terraform owns the ALB, target groups, listener and listener rules. [AWS controller documentation](https://kubernetes-sigs.github.io/aws-load-balancer-controller/latest/guide/targetgroupbinding/targetgroupbinding/) describes this ownership model.

The plan adds **57 resources**, with zero replacements/deletions. It creates no new EKS worker, RDS instance, NAT gateway or public ALB. The existing two nodes have 34 Pod slots; the conservative model including controller/API surges and a verification Pod uses 31 slots, 2,450 millicores and 3,084 MiB. Actual scheduling and target health must pass before publishing the frontend.

| Cost item | Planning amount |
| --- | ---: |
| Previously agreed foundation + 10C model | USD 54.41 |
| 10D reserve, including ALB/LCU and light hosting/API/log/network usage | USD 8.00 |
| Combined planning model | **USD 62.41** |
| User allowance | **USD 75.00** |

The AWS Mumbai price feed reports ALB USD 0.0239/hour and USD 0.008/LCU-hour. A conservative 168-hour model using one LCU throughout is USD 5.3592, within the 10D reserve. Actual remaining time to cleanup is shorter. See the [official regional price feed](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AWSELB/current/ap-south-1/index.json), [ELB pricing](https://aws.amazon.com/elasticloadbalancing/pricing/) and [Amplify pricing](https://aws.amazon.com/amplify/pricing/). The reserve assumes light demonstration traffic; taxes, retention, transfer and usage vary. It is not a live bill or enforced spending cap. The cleanup target remains **25 October 2026 at 6 PM Asia/Colombo**.

## 2. Security boundaries to understand

- Browser → Amplify and browser → Gateway use AWS-managed HTTPS endpoints. RDS connections retain `sslmode=verify-full` and the RDS CA bundle.
- Gateway → internal ALB and ALB → API Pods use **private HTTP** in this stage. Internal service-to-service calls also remain HTTP. Do not describe this as end-to-end TLS. A certificate/domain or internal TLS design and verification is separate work before a production security claim.
- ALB port 80 accepts only the VPC-link security group. API Pod port 8000 accepts the ALB security group. Controller webhook port 9443 is allowed only from the existing control-plane security group. No public CIDR ingress is added.
- Gateway JWT checks use the existing Cognito issuer and application client ID. Protected routes require `aws.cognito.signin.user.admin`, the standard Cognito **access-token scope**; this is not the Wonderland Administrators group. Python still validates access tokens, enforces Administrators membership and checks record ownership. Scope checking prevents accepting an ID token as an access token. See [AWS JWT authorizer validation](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-jwt-authorizer.html).
- No default/proxy route is exposed. Health, OpenAPI/docs, Booking's backend mock-payment endpoint and its backend staff-ticket lookup are excluded. Legitimate admin screens use exact protected routes; their Python group checks remain necessary.
- CORS is restricted to the exact generated Amplify origin. Gateway throttling is 5 requests/second with a burst of 20. Access logs retain request/route/status/latency metadata for seven days; no Authorization headers or request bodies are configured for logging.
- The controller's Pod role has read-only discovery and RegisterTargets/DeregisterTargets on the four exact target groups. It cannot create load balancers, security groups, IAM roles or read database secrets. The official chart's Kubernetes permissions support reconciliation; its watch namespace is `wonderland`.
- The frontend receives no database credentials, AWS keys, service-role credentials or signed upload URLs. The deployment script uses Amplify's signed upload URL only in memory and omits it from errors and evidence.

## 3. Review the prepared access and plan

Inspect `docs/evidence/step10d-routing-plan.json`, `step10d-access-review.json`, `step10d-policy-validation.json`, and the source under `infra/terraform/routing`.

Owner setup adds customer-managed policy **WonderlandRoutingDeployment** to WonderlandFeasibility and reprovisions account `708919751353`. Existing inline and workload policies remain unchanged. The new policy adds lifecycle/PassRole rights for one named controller role, listener-rule operations for the named ALB, Amplify app/main-branch deployment operations, the named Gateway log group and regional log-delivery/resource-policy operations.

Amplify assigns app IDs at creation, so app lifecycle rights use this account's Mumbai `apps/*` ARN prefix; this is broader than one pre-known app ID. App creation requires `Project=Wonderland`. Branch deployment actions are scoped to `main`. Regional CloudWatch log-delivery operations require wildcard resources. These scopes are part of the access review, not hidden by a claim that every permission targets one known ARN. No password-read permission is added.

## 4. Owner CloudShell: upload, validate, apply

After approval, upload `.local/deployment/step10d-access.zip` through CloudShell Actions. Compare the archive SHA-256 against `docs/evidence/step10d-access-bundle.json`:

```bash
aws sts get-caller-identity
sha256sum step10d-access.zip
step10d_dir=$(mktemp -d "$HOME/wonderland-step10d-bundle.XXXXXX")
unzip step10d-access.zip -d "$step10d_dir"
bash "$step10d_dir/apply-access-cloudshell.sh" --prepare
```

Preparation pins the policy and current inline-policy hashes, validates IAM and detects a conflicting existing managed policy. It makes no access change. After the reviewed access approval:

```bash
bash "$step10d_dir/apply-access-cloudshell.sh" --apply
```

Wait for `SUCCEEDED`. Do not attach this account-owned policy under AWS-managed policies; the helper uses a customer-managed policy reference. No keys, passwords or app resources are created by this owner helper.

## 5. CLI: apply only the reviewed Terraform plan

From `D:\Courses\Microservices`, using chamindu's non-root profile:

```powershell
. ./scripts/aws-common.ps1
& $LocalAws sts get-caller-identity --profile wonderland-feasibility
./scripts/deploy-cloud-routing.ps1 -ApplyInfrastructure
```

The runner verifies the account/role and saved plan/source hashes before applying. Routing has a separate encrypted/versioned state key, `demo/routing/terraform.tfstate`. Do not rerun a historical plan after it is marked applied; future changes need a fresh plan and review. If deployment partially succeeds, inspect saved state and generate a repair plan containing only missing/required resources.

## 6. Install reconciliation, set CORS and publish Angular

```powershell
./scripts/deploy-cloud-routing.ps1 -DeployFrontend
```

The runner:

1. Installs the official controller chart pinned to 3.6.0, with two bounded replicas, explicit region/VPC, existing Pod Identity and service auto-mutation/backend security-group management disabled. `keepTLSSecret: true` preserves the webhook certificate across upgrades.
2. Installs four TargetGroupBindings in `wonderland`. Terraform manages network rules; bindings do not request security-group changes.
3. Sets the exact Amplify origin in the existing application Helm values while retaining pricing projection and all mock flags. Waits for the API/worker rollout.
4. Waits for two healthy controller-registered IP targets per API. It never manually registers targets.
5. Builds Angular in production mode and writes the public runtime config into the build output only. It hides the local-only Metabase link on the hosted admin screen; cloud BI remains 10E.
6. Zips the contents of `frontend/dist/wonderland/browser` at the archive root. Calls Amplify CreateDeployment, uploads the archive, starts deployment and waits for success. See [Amplify manual deployment API](https://docs.aws.amazon.com/amplify/latest/APIReference/API_CreateDeployment.html).
7. Verifies HTTPS HTML/static assets, `/account`, `/bookings`, `/admin` and `/login` reloads, JSON runtime config, CORS, public catalog reads, all 26 unauthenticated denials, invalid JWT rejection and blocked backend paths.

Amplify's SPA rewrite preserves JS/CSS/JSON/assets while serving `index.html` for Angular routes. The configuration follows the [Amplify rewrite reference](https://docs.aws.amazon.com/amplify/latest/userguide/redirect-rewrite-examples.html). Runtime config uses `Cache-Control: no-store`.

## 7. Browser: authenticated walkthrough

Once the public checks pass, open the generated frontend URL from the deployment evidence. Sign in directly in Wonderland; keep the password and MFA codes in the app/AWS only. The previously local session does not carry to the new hosted origin.

For the separate visitor test, open Sign in → Create a visitor account. Use a second email address you control; enter a password with at least 12 characters, uppercase, lowercase, a number and a symbol, and confirm it. Submit the form yourself, enter the code from your email, then sign in. New users receive visitor access automatically. Do not add that account to Administrators. If the verification code expires, request another code in the app. Password/code entry must stay in Wonderland.

1. Open **Account** and confirm Python API verification identifies the correct visitor/administrator role.
2. As administrator, open protected attractions/pricing and visit-slot screens and confirm their data loads from cloud APIs.
3. Create a future visit booking, complete a clearly labeled **mock** checkout, and confirm its reference/tickets appear in My Bookings. Do not interpret this as provider payment integration.
4. With a separate visitor account, confirm administrator endpoints/screens are denied and another user's booking cannot be read. Record these tests only after using real separate sessions/accounts; changing client-side role display is not an authorization test.
5. Full simulated check-in/ride and connected cloud BI evidence continues in 10E. Provider sandbox, poison-message redrive, reliability and final assignment evidence remain on the completion tracker.

Authenticated checks require the user to enter credentials in the hosted app. Automated public checks alone cannot prove administrator/visitor/ownership behavior. No tokens or passwords should be copied to chat, shell history or evidence files.

Completed walkthrough: the existing administrator loaded cloud attractions, ticket pricing and visit slots, completed one mock checkout and viewed its demonstration ticket. The new visitor account completed signup/email verification/sign-in, received a real backend administrator-check **403**, was redirected away from `/admin`, and received **404** for the administrator's booking. The visitor then completed its own mock checkout and saw only its own confirmed booking in history. Sanitized Gateway request IDs/statuses are in `docs/evidence/step10d-authorization-log-metadata.json`; browser observations and mock references are in `step10d-browser-verification.json`. Two clearly marked mock bookings remain as demonstration evidence; neither collected money.

The Account page now confirms visitor restrictions using the normal authenticated HTTP client. It only displays “Administrator access is restricted” after the backend returns 403, and treats an expired token or unexpected administrator access as an error. Three focused Angular tests cover these outcomes.

## 8. Inspect and troubleshoot

```powershell
. ./scripts/aws-common.ps1
& ./.local/tools/helm/windows-amd64/helm.exe status aws-load-balancer-controller -n kube-system --kubeconfig .local/deployment/kubeconfig
& ./.local/tools/kubectl.exe --kubeconfig .local/deployment/kubeconfig -n wonderland get targetgroupbindings,pods,services
& ./.venv/Scripts/python.exe scripts/wait_routing_targets.py
& ./.venv/Scripts/python.exe scripts/verify_public_routing.py
```

For unhealthy targets, check controller Pod Identity, sanitized controller logs, port 8000 rules and readiness. Webhook timeouts require the control-plane-to-9443 rule and healthy controller replicas. A Gateway 503 can indicate a still-provisioning VPC link or missing healthy targets. A 401 can indicate a missing/expired access token or incorrect client/scope; keep the ID token out of Authorization. A route 404 should lead to the explicit route map, not adding a catch-all proxy. Do not relax certificate checks or print Secret YAML to troubleshoot.

## 9. Cleanup order and remaining evidence

At the agreed cleanup time, export evidence and inspect queued/outbox data. Remove frontend/Gateway routes and stop new traffic deliberately. Remove the routing Helm release (TargetGroupBindings) before deleting target groups, so the controller can deregister targets and finish finalizers. Destroy the routing Terraform root while the controller still exists, then uninstall the controller before EKS teardown. Follow the existing workload/foundation teardown and retention guide; preserve Cognito and older development messaging deliberately.

Verify the ALB, four target groups, VPC link ENIs, Gateway, Amplify app/branch and temporary routing rules are gone. Retained logs/state/images/snapshots may keep costing money. Owner deployment policy detachment is a separate deliberate access-cleanup step after teardown. No automatic cleanup or hard spending cap is configured.

Pre-deployment validation: Terraform validation and a 57-addition plan; IAM Access Analyzer zero findings; production Angular build; four routing/policy/binding tests; pinned controller render and fresh capacity review.

## 10. Deployment corrections and repeatability

The original apply created all 57 resources. The deployment then required these narrowly scoped corrections:

- EKS version suffix: the binding chart accepts the actual `1.35.8-eks-...` version through its explicit prerelease-compatible constraint.
- Controller upgrades: preserve the existing webhook TLS Secret, then restart controller replicas if a previous upgrade already generated mismatched trust. Certificate verification stays enabled.
- Amplify runtime authorization: CreateDeployment checks an additional `apps/d3vt08cs3xnlse/branches/main/deployments/*` ARN. The owner applied a hash-pinned version-2 policy correction for that exact existing app and branch, with zero Access Analyzer findings and unchanged inline permissions. The one-time helper intentionally rejects a changed/already-corrected baseline. Original preparation bundles are historical and must not be reapplied over the corrected policy.
- Amplify header serialization: AWS accepts a top-level `customHeaders` YAML object but returns a JSON array. Terraform ignores this representation difference and uses a semantic postcondition to fail if live header contents change. For an intentional header update, review a YAML update with the ignore temporarily removed, apply it, then restore the semantic guard and confirm a clean plan. A bare array is rejected by UpdateApp.
- ALB HTTP API compatibility: `strictest` desync mode caused ALB-generated HTTP 400 before requests reached Python. The repair plan changes only this attribute to `defensive`; desync protection remains enabled. See the [AWS troubleshooting article](https://repost.aws/knowledge-center/api-gateway-private-integration-errors). JWT, exact routes, CORS and private security groups remain unchanged.

Hosted frontend: **https://main.d3vt08cs3xnlse.amplifyapp.com**. Gateway: **https://n5viy353o3.execute-api.ap-south-1.amazonaws.com**. These demo endpoints are scheduled for teardown with the agreed environment; they are not permanent production addresses.

## 11. Final evidence and what comes next

- `docs/evidence/step10d-deployment-execution.json`: 57 resources, encrypted/versioned routing state, zero Terraform changes, final source hashes, Amplify job 2, USD 62.41 planning model and cleanup target.
- `docs/evidence/step10d-public-verification.json`: 23 passed public checks, including security headers, SPA reloads, catalog reads, CORS, all 26 protected-route unauthenticated denials, invalid JWT and blocked internal paths.
- `docs/evidence/step10d-live-verification.json`: 22 passed live infrastructure checks, four target groups with two healthy live Pod IPs each, two healthy controller replicas, exact route/JWT/network configuration and mock flags.
- `docs/evidence/step10d-browser-verification.json`: 15 observed checks using actual administrator and separate visitor sessions; sanitized server denial metadata and screenshots are linked from it.
- Local verification: four routing/policy/binding tests passed, three Account permission outcome tests passed, eight administrator form tests passed earlier in this stage, and the final Angular production build passed. Routing tests read checked-in route declarations and do not require an ignored local Terraform plan.

Step 10D is complete. Continue with **10E: hosted Metabase and the full mock check-in → ride usage → analytics walkthrough**, including durable BI metadata, restricted reporting access and purchase/revenue evidence. Review its incremental cost before creating further resources. Provider sandbox integration remains later work; keep checkout mock until that separate milestone. Actual AWS charges have not been reconciled by this deployment receipt, and USD 75 remains a planning allowance rather than a hard cap.
