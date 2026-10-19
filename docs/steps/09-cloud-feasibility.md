# Step 09 — prepare and run an isolated MOCK EKS / API Gateway experiment

The approved mock cloud test passed on **18 October 2026**: API Gateway reached the Python probe through its VPC link, internal ALB and EKS worker. All five test requests returned `MOCK`/`ok`; both pods were observed, and the booking path returned 404. **Step 09 is complete:** cleanup is verified, the experiment stack is absent, and all 18 resource categories checked are empty. See [results](../evidence/step09-cloud-results.json), [deployment prerequisites](09-deployment-access.md) and [validation evidence](../evidence/step09-validation.md).

Your Angular application, Python services, local database, mock payment/admission and Metabase keep their existing configuration. This experiment contains no booking records, real payment processing, Cognito tokens, database passwords or AWS application credentials.

## 1. Understand what we are testing

```text
Your browser / Python test
        | HTTPS GET /smoke/health
        v
API Gateway HTTP API (public AWS hostname; one public MOCK health route)
        | VPC link, private network connection
        v
Internal Application Load Balancer, port 80
        | instance target, NodePort 30080; security-group restricted
        v
EKS managed worker, t3.medium (one node)
        | Kubernetes Service
        v
Two small Python FastAPI probe pods, port 8000
```

The public route deliberately requires no login because its only response is non-sensitive probe metadata. It is not the application's authentication design. AWS supports HTTP API private integrations using a VPC link and an ALB **listener ARN**. The template removes the stage prefix using `overwrite:path` so the Python path stays `/smoke/health`. See the [AWS private integration documentation](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-develop-integrations-private.html).

The two subnets are in separate availability zones. For this short experiment, the single worker has a public IPv4 address for outbound ECR/API/image access, with no inbound internet security-group rules. The ALB is internal even though these subnets have an internet route. This avoids NAT gateway charges. It is a cost-conscious experiment; production private workers, endpoints/NAT, HTTPS inside the VPC, load balancer controller, workload IAM and stronger isolation belong in Step 10.

The ALB and its target group are CloudFormation resources. The publish script registers the experiment's one EC2 node as a target. There is no load balancer controller or automatic target reconciliation here. A replaced node requires re-running `publish`; this limitation is deliberate and must be mentioned in your report. Two pods on one worker do **not** demonstrate node fault tolerance or high availability.

## 2. Files and responsibilities

| File | Responsibility |
|---|---|
| `infra/feasibility/app/main.py` | Read-only `MOCK` health response; other application routes are absent |
| `infra/feasibility/Dockerfile` | Non-root Python image; uses existing resolved Python dependencies |
| `infra/feasibility/template.py` | Readable Python generator for the experiment's infrastructure |
| `infra/feasibility/cloudformation.json` | Generated deployable CloudFormation template |
| `scripts/cloud_feasibility.py` | Check, plan, status, deploy, publish, test and destroy commands |
| `scripts/verify_cloud_cleanup.py` | Read-only checks against saved resource IDs, disks and instance profiles after deletion |
| `tests/test_cloud_feasibility.py` | Mock route boundary, account/root guards, SSO principal and infrastructure checks |
| `.local/feasibility/` | Ignored account evidence, parameters, kubeconfig, manifests and test results |

We use CloudFormation for this bounded test because the project already uses it for Cognito and messaging and has AWS CLI installed. This is not the full Terraform/Helm platform planned in Step 10; that platform must reference or replace the experiment deliberately, rather than create duplicate clusters.

## 3. Restore temporary non-root access first

For this account's confirmed portal and first user setup, follow [Identity Center user, read-only assignment and CLI connection](09-identity-center-access.md). It uses the separate `wonderland-readonly` profile for inventory; pass `--profile wonderland-readonly` to the `check` command. That profile does not grant deployment access. The commands below use the separately authorized WonderlandFeasibility permission set for this experiment.

Open PowerShell in `D:\Courses\Microservices`.

```powershell
. .\scripts\aws-common.ps1
$env:PATH = "$(Split-Path $LocalAws);$env:PATH"
& $LocalAws configure sso --profile wonderland-feasibility
```

Enter the following when AWS prompts:

1. SSO session name: `wonderland-personal`.
2. Confirmed portal URL: `https://d-9f675820da.awsapps.com/start`.
3. Identity Center region: `ap-south-1`, confirmed for this account.
4. Registration scope: accept the default `sso:account:access`.
5. Complete browser sign-in and MFA directly in AWS.
6. Select account **708919751353** and permission set **WonderlandFeasibility**.
7. Default client region: `ap-south-1`; output: `json`.

Then verify:

```powershell
& $LocalAws sts get-caller-identity --profile wonderland-feasibility
```

Expected: account `708919751353`, usually an STS assumed-role ARN for Identity Center. It must not end with `:root`. Later sessions use:

```powershell
& $LocalAws sso login --profile wonderland-feasibility
```

Do not create or paste long-lived access keys. The existing `wonderland-dev` profile is not suitable for this deployment because its saved login identity is root. If your portal cannot offer this account, confirm the account assignment with the Identity Center administrator. A Cognito application administrator is unrelated to AWS infrastructure permissions.

Official instructions: [AWS CLI Identity Center configuration](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sso.html).

## 4. Run the read-only account check

```powershell
& .\.venv\Scripts\python.exe scripts/cloud_feasibility.py check --profile wonderland-readonly
```

The lifecycle default profile is `wonderland-feasibility`; the commands spell it out to avoid selecting an old root-backed profile. The command fixes the expected account and Mumbai region. It saves `.local/feasibility/account-check.json`, checks the temporary identity, then attempts reads for:

- Availability zones and currently offered EKS versions/support status.
- Existing EKS clusters, HTTP APIs, VPC links, VPCs, ALBs and ECR repositories.
- EC2, EKS, VPC, load balancer and API Gateway service quotas.
- The earlier messaging stack and Cognito pool, for inventory only.

Each result is `READ_OK` or `UNVERIFIED` with the actual API error. Failed authentication stops the check immediately. Do not treat missing access as an empty account. Read success does not prove permission to create, tag, pass IAM roles or delete resources. Quota values also need comparison against **current usage**, pending allocations and service restrictions; they are not spare capacity guarantees.

Before deployment, review at least:

| Check | Needed for this experiment |
|---|---|
| Account and principal | Correct account; non-root identity; stable IAM role resolved with `iam:GetRole` |
| Region/AZs | Mumbai enabled; at least two available standard AZs |
| EKS | Room for one additional cluster, node group and access entry |
| EC2 | At least two available Standard On-Demand vCPUs for one t3.medium, plus current account usage |
| VPC | Room for one VPC, internet gateway, route table, two subnets, four explicit SGs and EKS-managed SG/ENIs |
| Load balancing | Room for one ALB, listener and target group |
| API Gateway | Room for an HTTP API and VPC link; ENI capacity available |
| IAM | EKS/EC2 trusted roles, attach/detach policies, instance profile operations, `iam:PassRole`, access entry administration; service-linked role creation when absent |
| Other actions | CloudFormation lifecycle, EKS lifecycle, EC2 networking/launch templates, Auto Scaling, ELB, ECR push, API Gateway V2 and resource tagging/deletion |

An administrator should review these provisioning capabilities against the template and your permission set. A successful change set validates the template, not every downstream permission or quota. Real deployment is the final feasibility proof. Do not grant broad infrastructure permissions to the existing application event-worker roles.

## 5. Review cost and set a short test window

EKS is billable while the cluster exists, even when no user requests are sent. Stopping Angular or deleting pods does not stop EKS/ALB charges. AWS lists **$0.10 per cluster-hour for standard support** and higher extended-support fees. The template sets `STANDARD` and the plan command verifies regional version support at execution time. AWS may automatically upgrade a retained cluster at the end of standard support. See [EKS pricing](https://aws.amazon.com/eks/pricing/) and [version policy](https://docs.aws.amazon.com/eks/latest/userguide/view-upgrade-policy.html).

Use the [AWS Pricing Calculator](https://calculator.aws/) with **Asia Pacific (Mumbai)** for the current regional quote before execution:

| Item | Configuration to price |
|---|---|
| EKS control plane | One cluster, standard support, whole experiment lifetime |
| EC2 | One Linux t3.medium, On-Demand; include possible T3 surplus CPU credits |
| EBS | 20 GiB gp3 root disk, prorated storage |
| IPv4 | One worker public IPv4; AWS lists $0.005/address-hour before applicable credits |
| ALB | One internal ALB and low-traffic LCUs; hourly minimums may apply |
| HTTP API | A handful of requests; regional request/data pricing |
| ECR | One Python image's storage, scanning/transfer charges if applicable |
| Miscellaneous | Data transfer, any logging and applicable taxes |

For planning only, allow roughly **US$0.20–0.40/hour** for this tiny experiment, plus usage/minimums/tax; this range is **not a verified Mumbai quote or a maximum**. Keeping it for a month could cost hundreds of dollars. A suggested learning window is two hours with US$5 budget headroom. Confirm the quote, your remaining credits and the time window personally before deployment. Do not assume a personal account's free tier covers EKS. Pricing references: [ALB](https://aws.amazon.com/elasticloadbalancing/pricing/), [API Gateway](https://aws.amazon.com/api-gateway/pricing/), [IPv4](https://aws.amazon.com/vpc/pricing/).

In Billing and Cost Management, review current spend and credits, and optionally create an AWS Budget for the experiment. A budget notification is delayed and is not a spending cap. Nothing in these scripts automatically shuts down AWS or caps spending; plan to run cleanup in the same session.

## 6. Install a matching kubectl locally

The Docker Desktop client is **1.32.2**. A compatible **1.35.9** client is now installed and checksum-verified in `.local/tools/kubectl.exe`; the proposed cluster is **1.35**. Version 1.35 is an initial choice, not a permanent assumption; `plan` queries current Mumbai support before proceeding. AWS's [version calendar](https://docs.aws.amazon.com/eks/latest/userguide/kubernetes-versions.html) currently lists 1.35 in standard support. The commands below recreate the local client when needed.

This installs the latest patch of the 1.35 client into the ignored project tool folder and verifies the published checksum:

```powershell
$clientVersion = (Invoke-RestMethod https://dl.k8s.io/release/stable-1.35.txt).Trim()
$clientPath = Join-Path $PWD '.local\tools\kubectl.exe'
New-Item -ItemType Directory -Force (Split-Path $clientPath) | Out-Null
Invoke-WebRequest "https://dl.k8s.io/release/$clientVersion/bin/windows/amd64/kubectl.exe" -OutFile $clientPath
$expectedHash = (Invoke-RestMethod "https://dl.k8s.io/release/$clientVersion/bin/windows/amd64/kubectl.exe.sha256").Trim()
if ((Get-FileHash -LiteralPath $clientPath -Algorithm SHA256).Hash -ine $expectedHash) {
    throw 'kubectl checksum mismatch; do not execute the download'
}
& $clientPath version --client
```

The script prefers that local executable and rejects unsupported client/server skew. Follow the [official Windows kubectl instructions](https://kubernetes.io/docs/tasks/tools/install-kubectl-windows/) if changing Kubernetes versions. Terraform, Helm and eksctl are not required for this experiment.

## 7. Validate locally and create an unexecuted change set

```powershell
& .\.venv\Scripts\python.exe infra/feasibility/template.py
& .\.venv\Scripts\python.exe -m pytest tests/test_cloud_feasibility.py -q
```

Find your current **public IPv4**, for example using `Invoke-RestMethod https://checkip.amazonaws.com`. Use a single `/32`; a LAN address such as `192.168...` is not your public address. VPN/network changes can change it. Then replace the example below:

```powershell
& .\.venv\Scripts\python.exe scripts/cloud_feasibility.py plan --profile wonderland-feasibility --operator-cidr YOUR_PUBLIC_IPV4/32
& .\.venv\Scripts\python.exe scripts/cloud_feasibility.py status --profile wonderland-feasibility
```

`plan` performs AWS template validation, resolves your permanent IAM principal, verifies the chosen EKS version is in standard support and submits a **CREATE change set** for stack `wonderland-step09-mock`. It does not execute infrastructure. The shell stack remains `REVIEW_IN_PROGRESS`; the change set must become `CREATE_COMPLETE` / `AVAILABLE`. Inspect the resource list and IAM capabilities. Every infrastructure change should be an addition for this experiment; existing Cognito/messaging resources are not part of it.

This command creates a review object in AWS, so it requires CloudFormation permissions even though it does not launch the billable infrastructure. It is create-only. If parameters need correction before execution, delete this experiment's review stack with the guarded cleanup command below, then plan again. Do not reuse an application stack name or execute an old plan after changing the template.

## 8. Deploy only after reviewing the cost and change set

```powershell
& .\.venv\Scripts\python.exe scripts/cloud_feasibility.py deploy --profile wonderland-feasibility --approve-billable-resources
& .\.venv\Scripts\python.exe scripts/cloud_feasibility.py status --profile wonderland-feasibility
```

The explicit flag acknowledges billable resources; it is not a cost cap. Stack creation is asynchronous. Check progress periodically, or use the AWS CloudFormation console in Mumbai. Allow time for the control plane, node group and VPC link. Proceed only when the stack is `CREATE_COMPLETE`. If it fails or rolls back, inspect the first substantive failure in stack events, then clean up instead of leaving partial infrastructure overnight.

The template creates its own EKS access entry for your resolved IAM user/role; root and STS session ARNs are not used. Cluster creator's implicit administrator permission is disabled. Managed nodes get the EKS/CNI/ECR permissions required for this temporary probe. They do not get permission to access the application database, Cognito administrators or event worker roles. IMDSv2 is required and pod access to node metadata is restricted by hop limit. The pod has no mounted service-account token.

## 9. Build, push and publish the Python probe

Keep Docker Desktop's Linux engine running:

```powershell
& .\.venv\Scripts\python.exe scripts/cloud_feasibility.py publish --profile wonderland-feasibility
& .\.venv\Scripts\python.exe scripts/cloud_feasibility.py status --profile wonderland-feasibility
```

The command:

1. Rechecks account/non-root identity and the actual cluster/client version.
2. Builds a Linux/amd64 image from the small probe Dockerfile using a unique timestamp tag.
3. Gets a temporary ECR password directly from AWS CLI and sends it to Docker through stdin.
4. Keeps Docker's registry configuration under ignored `.local/feasibility/docker`, then pushes the image.
5. Resolves the ECR digest and uses that immutable digest in Kubernetes.
6. Writes a separate `.local/feasibility/kubeconfig`, leaving your default kubeconfig unchanged.
7. Applies the `wonderland-smoke` namespace, two-pod Deployment and NodePort Service.
8. Waits for rollout and registers the dedicated EC2 node in the internal ALB target group.
9. Saves the worker, disk and Auto Scaling inventory for later cleanup verification.

The pods run as UID 10001 with a read-only filesystem, dropped capabilities, resource requests/limits, readiness and liveness probes. The existing pinned service requirements are reused to keep dependency versions consistent; optimizing this probe image is optional later.

Wait until `status` shows the ALB target is `healthy`. Health initially fails before pods and targets are installed; that is expected. Re-running `publish` creates another immutable image tag; clean up the experiment's ECR repository at the end. Temporary Docker authorization is still sensitive: keep `.local` ignored and do not share it.

## 10. Test the full cloud path and collect evidence

```powershell
& .\.venv\Scripts\python.exe scripts/cloud_feasibility.py test --profile wonderland-feasibility
```

The script makes five HTTPS calls through the **API Gateway endpoint**, checks `status=ok` and `mode=MOCK`, records latency and pod metadata, and verifies an application booking path returns 404. Evidence is saved to `.local/feasibility/cloud-test.json`. Expected body:

```json
{"service":"wonderland-cloud-probe","mode":"MOCK","status":"ok","pod":"mock-probe-..."}
```

Five requests prove connectivity at that moment; they do not prove load capacity or availability. Do not claim pod load balancing unless both pod identities are actually observed. You may also open the output `ApiEndpoint` plus `/smoke/health` in a browser. Keep Angular pointed at the local APIs; do not substitute this probe URL into the application configuration.

For assignment evidence, save the UTC timestamp, account/region, stack status, EKS version, node readiness, pod readiness, private ALB target health, VPC link status and five API responses. Record the elapsed deployment/test/cleanup times and actual costs when billing catches up. Redact secrets; never publish kubeconfig, Docker config or AWS caches. Copy only reviewed public test results to `docs/evidence` if submitting them.

## 11. Clean up in the same session

```powershell
& .\.venv\Scripts\python.exe scripts/cloud_feasibility.py destroy --profile wonderland-feasibility --confirm-stack wonderland-step09-mock
& .\.venv\Scripts\python.exe scripts/cloud_feasibility.py status --profile wonderland-feasibility
```

Deletion requires the exact experiment stack name and the ownership tag `Purpose=Step09MOCK`. The script saves the stack's outputs before deletion to help verify cleanup. The experiment's ECR repository is configured to empty on deletion, so its probe images will be deleted too. Kubernetes objects disappear with the cluster.

Deletion is asynchronous. Once complete, `status` will report that the stack does not exist. If it shows `DELETE_FAILED`, inspect the specific resource and remove only the experiment-owned dependency; then retry deleting this stack. Do not delete shared account resources or the earlier application stacks. An expired login must be renewed before cleanup can finish.

Verify in Mumbai that the experiment's EKS cluster, node EC2 instance/Auto Scaling group, ALB/target group, API, VPC link, ECR repository, EBS disk and VPC/ENIs are gone. Use saved stack outputs/resource IDs and tags to identify them; `list-clusters` returning other clusters is not a cleanup failure. Check IAM roles created by this stack are gone as well; AWS service-linked roles can remain and do not themselves incur a runtime charge. Check the Billing page later for usage that has not yet posted. Removing just the API does not stop cluster/node/ALB billing.

After the stack is absent, run the read-only verifier. It needs the inventory saved by a successful `publish` and the resource list saved by `destroy`:

```powershell
& .\.venv\Scripts\python.exe scripts/verify_cloud_cleanup.py --profile wonderland-feasibility
```

Expect `verified: true`, zero remaining counts, and the original messaging stack and Cognito pool still present. It saves `.local/feasibility/cleanup-verification.json`. AccessDenied fails verification; it is never interpreted as resource absence. For a failed deployment before publishing, inspect that attempt's saved CloudFormation resource IDs directly instead.

Optionally discard the local temporary registry login after cleanup:

```powershell
docker --config .local/feasibility/docker logout 708919751353.dkr.ecr.ap-south-1.amazonaws.com
```

## 12. Troubleshooting and completion checklist

| Symptom | Next check |
|---|---|
| Session expired / root identity | Correct SSO portal, region, account and permission set; renew login |
| `iam:GetRole` denied | Operator needs read access to resolve the full role path for the EKS access entry |
| AccessDenied while creating | Exact failing action in CloudFormation events; permission boundary/SCP/PassRole/service-linked-role permissions |
| EC2 limit or capacity error | Current regional quota/usage and instance availability; request quota or review a deliberate instance-type change |
| Nodes cannot join | Public subnet IP assignment, internet route, custom security groups, node role, current AMI/version |
| kubectl timeout | Current public `/32`, VPN/proxy, endpoint access and network reachability |
| kubectl Unauthorized | Same SSO role as the planned OperatorArn, correct kubeconfig and EKS access entry |
| ImagePullBackOff | ECR digest, node pull policy, image platform and node outbound connectivity |
| Pod not ready | `kubectl --kubeconfig .local/feasibility/kubeconfig -n wonderland-smoke describe pods` and pod logs |
| Target unhealthy / gateway 503 | Pod readiness, node instance target/NodePort, ALB-to-node SG rule and health path |
| Gateway backend 404 | Exact route and integration path mapping; stage prefix must be removed |
| Node replaced | Re-run publish to register its replacement; target reconciliation is manual in this experiment |
| Deletion failed | Stack events and experiment-owned ENI/LB dependencies; verify deletion rather than assuming it succeeded |

Step 09 is complete only after: non-root account access and readiness are recorded, the approved experiment reaches `CREATE_COMPLETE`, the probe is healthy through API Gateway, evidence is saved, and cleanup is verified (or explicitly budgeted retention is agreed). The 18 October run met these exit conditions; see the saved cloud-test and cleanup evidence. Step 10 then replaces this minimal smoke architecture with the complete application platform, protected application routes and repeatable Terraform/Helm deployment.
