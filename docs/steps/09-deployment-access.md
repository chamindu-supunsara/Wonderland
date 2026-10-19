# Step 09 — account readiness passed; prepare deployment access

The read-only checks on **17 October 2026** succeeded in account `708919751353`, region `ap-south-1`. The application continues using its local mock configuration.

**Latest status:** the approved fourth deployment reached CREATE_COMPLETE and the mock API Gateway-to-EKS test passed. Five responses returned MOCK/ok, both pods were observed and the booking route returned 404. Cleanup is verified: the experiment stack is absent and all 18 checked resource categories are empty. Step 09 is complete. The owner policy and API Gateway service-role bootstrap are complete. See [current evidence](../evidence/step09-validation.md).

## What we verified

| Item | Account result | Experiment needs |
|---|---|---|
| Identity | Non-root `AWSReservedSSO_WonderlandReadOnly` session, user `chamindu` | Temporary non-root identity |
| Availability zones | Mumbai 1a, 1b, 1c available; t3.medium offered in all three | Two AZs; one worker |
| Standard On-Demand vCPU quota | 5; no pending/running/stopping EC2 instances found | 2 vCPUs for t3.medium |
| EKS clusters | 0; cluster quota 100 | 1 |
| VPCs | 1; quota 5 | 1 additional |
| Internet gateways | 1; quota 5 | 1 additional |
| ALBs | 0; quota 50 | 1 |
| API Gateway V2 VPC links | 0; V2 quota 10 | 1 |
| HTTP APIs / ECR repositories | 0 / 0 | 1 / 1 |
| Kubernetes 1.35 | Regional STANDARD_SUPPORT; standard support ends 27 March 2027 | Standard support |
| Prior messaging | `wonderland-events-dev` CREATE_COMPLETE | Preserve |
| Prior Cognito | Pool `ap-south-1_aBuDlZ9RC` readable | Preserve |
| AWS template validation | Accepted; requires CAPABILITY_IAM | Review IAM creation |

Quotas and listings are point-in-time observations. They do not reserve capacity, prove all future API calls or establish the current account plan/credit balance. The EC2 scan does not measure unrelated services' resources; the experiment uses a separate VPC. AWS IAM simulation returns **implicitDeny** for the sampled CloudFormation, EKS, EC2, IAM, ECR, ALB and API Gateway provisioning actions under the read-only role. This is expected: keep that role read-only.

The matching project-local kubectl **v1.35.9** is installed and checksum-verified. The Python probe image has also been built and tested locally as non-root with a read-only filesystem and no external network; health returned MOCK/200 and application/admin/docs paths returned 404. It has not been pushed to ECR or deployed.

## Cost review

The AWS Price List API returned these Mumbai On-Demand rates:

| Component | Rate before tax/credits |
|---|---|
| One Linux t3.medium | US$0.0448/hour |
| Internal Application Load Balancer | US$0.0239/hour or partial hour |
| ALB usage | US$0.008/LCU-hour; usage dependent |
| gp3 disk | US$0.0912/GB-month; 20 GB = US$1.824/month prorated |
| HTTP API | US$1.05/million requests in the first tier |

AWS's [EKS pricing](https://aws.amazon.com/eks/pricing/) lists US$0.10/cluster-hour for standard support, and [VPC pricing](https://aws.amazon.com/vpc/pricing/) lists US$0.005/public IPv4 address-hour. The cluster template uses standard support and does not enable EKS Auto Mode or a provisioned-control-plane tier.

Using a 730-hour month solely to prorate the disk, the baseline is approximately **US$0.1762/hour**, or **US$0.1842/hour with an assumed one LCU/hour**. Two hours at that assumed steady state is about **US$0.37**, before image storage, transfer, possible T3 surplus credits, request billing, partial-hour minimums and taxes. ECR's regional price query returned no products, so its storage rate has not been quoted here. These calculations are an estimate, not an invoice or cap.

Suggested test allowance: two hours with US$5 headroom, followed by verified cleanup. Control-plane creation/deletion time also matters. No budget approval has been assumed, no credit balance was read and no budget resource was created. Recheck Billing/Credits after organization creation before proceeding. Billing alerts do not enforce a hard spending cap.

## 1. Review the prepared deployment policy

Open `infra/feasibility/operator-policy.json`. This policy is intended to be combined with AWS managed **ReadOnlyAccess** in a separate permission set named **WonderlandFeasibility**.

AWS IAM Access Analyzer validated the final JSON with **zero findings**. Validation checks policy syntax and known policy issues; it does not prove every CloudFormation call will succeed or certify least privilege.

Its important limits:

- CloudFormation lifecycle: only `wonderland-step09-mock` and the `step09-create` change set name.
- EKS lifecycle/access entries: only that experiment cluster and its child resources.
- ECR writes: experiment-named repositories in this account and Mumbai.
- IAM role lifecycle: only the experiment's generated ClusterRole and NodeRole names.
- Attachable role policies: only the four managed cluster/node/CNI/image-pull policies used by the template.
- PassRole: only those experiment roles to EKS or EC2.
- Service-linked role creation: only the listed EKS/nodegroup/Auto Scaling/ELB services.

**EC2 networking/launch and ALB permissions have broader scope within Mumbai. API Gateway writes cover HTTP APIs and VPC links in Mumbai. This is not a complete isolation boundary:** while assigned, this trusted developer role can affect other matching regional infrastructure and can incur costs. IAM/network role permissions are powerful even without AdministratorAccess. Use a one-hour session, keep the read-only profile for routine inventory and remove the deployment assignment after cleanup if you no longer need it. No permission to alter Cognito user pools or SNS/SQS resources is added by this policy.

The API Gateway statement now uses `apigateway:*` on these same regional resource paths because the live Stage and VPC-link handlers required tagging authorization not covered by the earlier enumerated HTTP-verb actions. IAM Access Analyzer reports zero findings on the revised policy, but that does not guarantee successful deployment. Apply the update through the owner/setup console: upload the current `operator-policy.json` and `apply-operator-policy-cloudshell.sh` into CloudShell, then run `bash apply-operator-policy-cloudshell.sh`. It preserves the managed ReadOnlyAccess attachment and the rest of the prepared inline policy. On error, capture the exact command/error; do not grant AdministratorAccess to work around it. File-not-found, a stale uploaded JSON file and AccessDenied require different fixes.

On 18 October the reproduced error was `bash: apply-operator-policy-cloudshell.sh: No such file or directory` (exit 127). Both files were initially missing from the Mumbai owner's `/home/cloudshell-user`. Upload both files to the **same user and region** where you run the command, wait for upload success, and verify with `ls -l`. CloudShell homes are tied to the environment; having a local Windows file does not place it in CloudShell. The current files were subsequently uploaded and checksum-verified. To capture a rerun without discarding the script's true exit status:

```bash
bash apply-operator-policy-cloudshell.sh operator-policy.json 2>&1 | tee step09-policy-rerun.log
result=${PIPESTATUS[0]}
printf 'Script exit code: %s\n' "$result"
```

### One-time API Gateway service-linked role prerequisite

Check from the deployment profile:

```powershell
& $LocalAws iam get-role --role-name AWSServiceRoleForAPIGateway --profile wonderland-feasibility
```

If AWS reports NoSuchEntity, an authorized owner/setup administrator must create the standard role before deploying a VPC link. This bounded developer policy intentionally does not allow creating the API Gateway service-linked role. In owner CloudShell, with approval for this account-level access change:

```bash
aws iam create-service-linked-role --aws-service-name ops.apigateway.amazonaws.com
```

The trust service is **ops.apigateway.amazonaws.com**. On 18 October this account's bootstrap succeeded and trust was verified, so it does not need repeating. Keep the role after experiment cleanup; it is an AWS-managed prerequisite with no runtime charge. See [AWS API Gateway service-linked roles](https://docs.aws.amazon.com/apigateway/latest/developerguide/using-service-linked-roles.html).

## 2. Create WonderlandFeasibility using the owner/setup console

Your **WonderlandReadOnly console session cannot create permission sets**. Use the existing account-owner/authorized administrator setup session for these steps:

1. Open **IAM Identity Center → Permission sets → Create permission set**.
2. Choose **Custom permission set**.
3. Under AWS managed policies, add **ReadOnlyAccess**.
4. Under inline policy, paste the complete contents of `infra/feasibility/operator-policy.json`.
5. Leave customer managed policies and permission boundary empty for this prepared policy, unless you already have an administrator-defined boundary that must apply.
6. Name: **WonderlandFeasibility**; session duration: **1 hour**; leave relay state empty.
7. Review the policy scope and create the permission set.
8. Open **AWS accounts → 708919751353 → Assign users or groups**.
9. Select existing user **chamindu**, then **WonderlandFeasibility**, review and submit.
10. Wait for assignment/provisioning to succeed. Leave the existing WonderlandReadOnly assignment intact.

If the console reports an inline-policy or boundary error, keep the exact error for diagnosis. Do not replace the policy with AdministratorAccess just to bypass an error. Creating this assignment grants privileges but does not itself deploy the EKS stack. See [AWS account assignment instructions](https://docs.aws.amazon.com/singlesignon/latest/userguide/assignusers.html).

### Fix: Not supported policy arn:aws:iam::708919751353:policy/ReadOnlyAccess

This error occurred during assignment and was confirmed through read-only inspection: WonderlandFeasibility had a **customer-managed policy reference** named ReadOnlyAccess and no attached AWS-managed policies. Its inline policy correctly matched the prepared operator policy, and there was no permission boundary.

In the owner/setup console, open **IAM Identity Center → Permission sets → WonderlandFeasibility → Permissions**:

1. Remove the `ReadOnlyAccess` reference under **Customer managed policies**.
2. Under **AWS managed policies**, attach **ReadOnlyAccess**, whose ARN must be `arn:aws:iam::aws:policy/ReadOnlyAccess`.
3. Keep the existing inline policy. No replacement policy needs to be created in IAM.
4. Save changes and choose **Update/Reprovision accounts** if the console offers it for an existing assignment.
5. Retry **AWS accounts → 708919751353 → Assign users or groups → chamindu → WonderlandFeasibility** and wait for success.

The account-number ARN in the error refers to an account-owned policy that does not exist. The correct AWS-managed policy uses `aws` in that ARN field. This configuration repair has been diagnosed, not applied through the read-only CLI session. See [AWS policy reference](https://docs.aws.amazon.com/aws-managed-policy/latest/reference/ReadOnlyAccess.html).

### Fix: feasibility login works but iam:GetRole is denied

A later verification found that the user assignment exists and the new role can sign in, but WonderlandFeasibility's **AWS-managed policy list is empty**. Its provisioned IAM role has **AmazonEC2ReadOnlyAccess**, which covers EC2 only, plus the inline operator policy. That combination does not provide IAM/EKS/CloudFormation discovery reads.

In the owner/setup console, attach exactly **ReadOnlyAccess** (`arn:aws:iam::aws:policy/ReadOnlyAccess`) under **this permission set's AWS managed policies**. Confirm it appears in the saved list. Because the account assignment already exists, run **Update/Reprovision accounts** for `708919751353` and wait for success. Merely modifying the definition does not establish that the existing account role received it. Keep the inline policy. After updating, renew CLI sign-in if necessary and verify the role again. Do not choose the similarly named AmazonEC2ReadOnlyAccess policy as the account-wide read policy.

A subsequent successful update attached three similarly named policies instead: AIDevOpsAgentReadOnlyAccess, AIOpsReadOnlyAccess and AgentRegistryReadOnlyAccess. The exact AWS-wide ReadOnlyAccess policy remained absent. For a deterministic correction, run `infra/feasibility/repair-readonly-cloudshell.sh` in **AWS CloudShell from the owner/authorized Identity Center administrator console**. It verifies the account and permission-set name, attaches the exact AWS-wide policy, removes only those three unintended policies when present, and requests reprovisioning for this account. It preserves the inline policy and creates no experiment infrastructure. The ordinary WonderlandFeasibility/ReadOnly sessions cannot perform this administrative repair.

## 3. Connect a separate CLI deployment profile

From PowerShell in `D:\Courses\Microservices`:

```powershell
. .\scripts\aws-common.ps1
& $LocalAws configure sso --profile wonderland-feasibility
```

Use these values:

```text
SSO session name: wonderland-personal
SSO start URL (if asked): https://d-9f675820da.awsapps.com/start
SSO region (if asked): ap-south-1
SSO registration scopes (if asked): sso:account:access
Account: 708919751353
Role/permission set: WonderlandFeasibility
Default client region: ap-south-1
Output: json
```

Complete AWS browser login/MFA if prompted. Then:

```powershell
& $LocalAws sso login --profile wonderland-feasibility
& $LocalAws sts get-caller-identity --profile wonderland-feasibility
```

Expected ARN contains **AWSReservedSSO_WonderlandFeasibility**. The account must be `708919751353`. Do not use the read-only or root profile for deployment. Existing worker-source configuration is separate and is not corrected automatically by this assignment.

## 4. Create and review an unexecuted change set

Once the new role is available, obtain your current public IPv4 address. Use the single address with `/32`:

```powershell
& .\.venv\Scripts\python.exe scripts/cloud_feasibility.py plan --profile wonderland-feasibility --operator-cidr YOUR_PUBLIC_IPV4/32
& .\.venv\Scripts\python.exe scripts/cloud_feasibility.py status --profile wonderland-feasibility
```

The CREATE change set is reviewable and is **not automatically executed**. Verify resource additions, the exact cluster-admin OperatorArn, Kubernetes 1.35 and your public `/32`. If it fails, inspect the actual error; the new policy has not yet been tested by a real stack creation.

After the change set and budget are reviewed, use the [main Step 09 guide](09-cloud-feasibility.md) for deploy, publish, test and destroy, **adding `--profile wonderland-feasibility` to every lifecycle command**. Read-only discovery, policy validation and a reviewed plan do not replace approval of the billable run. Keep the application in mock mode throughout; this is only an isolated health probe.
