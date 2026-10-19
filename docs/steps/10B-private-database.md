# Step 10B — private database bootstrap

Status: **completed and live verified on 18 October 2026**. All five migration chains passed against private RDS with TLS 1.3; four attractions, four ticket tiers and 21 visit slots were seeded. Temporary AWS and Kubernetes bootstrap access has been removed and independently verified. See [database evidence](../evidence/step10b-database-verification.json) and [cleanup evidence](../evidence/step10b-cleanup-verification.json).

Checkout remains mock. This stage uses the existing private RDS instance and EKS workers; it adds no RDS instance, EC2 worker, NAT gateway or public database endpoint. It does not deploy the application APIs or Angular frontend (10C/10D).

The following procedure records the completed execution and supports a deliberate recovery rehearsal. Do not rerun it during normal application startup or recreate the temporary role unless a reviewed administrative task requires it.

## 1. Review access before running anything

Account `708919751353`, region `ap-south-1`, operator profile `wonderland-feasibility` (chamindu). Use the owner/setup CloudShell session only for the reviewed access helper.

The operator receives five ECR upload actions on **only** `wonderland-demo/catalog`. It receives no new permission to read database passwords. The combined existing inline policy is 10,102 bytes; the limit is 10,240, so further additions require another review.

Temporary CloudFormation stack `wonderland-db-bootstrap-access` contains exactly two resources: IAM role `wonderland-demo-db-bootstrap` and its EKS Pod Identity association. The association is restricted to cluster `wonderland-demo`, namespace `wonderland-bootstrap`, service account `db-bootstrap`. The role can read the existing RDS master secret and read/write only the five existing application secrets. Passwords are processed inside the private bootstrap Pod, never in the browser, shell output, source code or Terraform state.

Review `infra/database/operator-policy.json`, `infra/database/bootstrap-access.json`, `infra/database/apply-access-cloudshell.sh`, and `docs/evidence/step10b-access-review.json` before approval. The helper pins both new documents and the existing policy hash, backs up the current policy, checks for drift, validates IAM policies and validates the template before changing access.

## 2. Owner CloudShell: upload and prepare

Upload `.local/deployment/step10b-access.zip` using CloudShell **Actions → Upload file**. Compare its SHA-256 with `docs/evidence/step10b-bundle.json`. Extract into a new directory so older helper files cannot be selected accidentally:

```bash
aws sts get-caller-identity
sha256sum step10b-access.zip
task_dir=$(mktemp -d "$HOME/wonderland-step10b-bundle.XXXXXX")
unzip step10b-access.zip -d "$task_dir"
bash "$task_dir/apply-access-cloudshell.sh" --prepare
```

Confirm the account is correct and this is the owner/setup administrator, not WonderlandFeasibility/ReadOnly. Preparation validates only; it does not deploy or grant access. After explicit approval for the reviewed access changes:

```bash
bash "$task_dir/apply-access-cloudshell.sh" --apply
```

Wait for account provisioning and the temporary stack to finish. If either fails, save the exact AWS error and stop; do not replace policies with broad administrator access.

## 3. Local CLI: run the private bootstrap

Run from `D:\Courses\Microservices`:

```powershell
. ./scripts/aws-common.ps1
& $LocalAws sts get-caller-identity --profile wonderland-feasibility
./scripts/bootstrap-cloud-database.ps1
```

The script verifies the operator and reviewed policy, checks the temporary stack, builds the bootstrap image, uploads an immutable image tag to the existing catalog ECR repository, resolves its digest, and installs the temporary Helm Job. Temporary Docker credentials are removed after upload. Helm receives only resource identifiers and the image digest.

The Kubernetes prerequisites create restricted namespaces and five empty runtime Secret placeholders without writing passwords to manifests. The Job can patch only those five named Secrets. Do not use `kubectl get secrets -o yaml`, print connection URLs, or copy passwords into `.env` files to troubleshoot.

The bootstrap performs these steps:

1. Read the RDS-managed master secret using Pod Identity and connect through private networking with `sslmode=verify-full` and the official AWS RDS CA bundle.
2. Acquire a database advisory lock. Create five non-login schema-owner roles and five separate runtime logins: catalog, booking, payment, admission and analytics.
3. Reuse credentials already prepared in Secrets Manager on retry. Publish a `ready` status only after migrations and checks succeed; runtime passwords are generated in the Pod.
4. Run all five Alembic migration chains using their schema-owner roles. API runtime users receive their own schema's DML privileges, no schema creation, no other service schema access and no migration metadata access.
5. Create the reporting schema and a views-only non-login reporting role. Prepare the isolated logical database `wonderland_metabase` with a non-login owner. Metabase login provisioning and connection are completed in 10E.
6. Seed four attractions, four ticket tiers and at least 21 future visit slots. Preserve existing administrator edits. Do not create Cognito users or fabricated purchases.
7. Verify runtime connections use TLS, cross-schema/DDL access is denied, aggregate views work, and a hostname-mismatched certificate connection is rejected.
8. Write runtime-only connection URLs to the five existing Secrets Manager secrets and five Kubernetes Secrets. Their CA path matches the five service Dockerfiles.
9. Emit a sanitized `BOOTSTRAP_REPORT` and save `docs/evidence/step10b-database-verification.json` locally. Successful completion is `status: VERIFIED`, all five expected migration heads, and `checkout: mock`.

TLS verification uses the [official RDS SSL guidance](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/PostgreSQL.Concepts.General.SSL.html). Temporary credentials follow [EKS Pod Identity](https://docs.aws.amazon.com/eks/latest/userguide/pod-id-role.html). The image's pinned SDK supports the [Pod Identity credential provider](https://docs.aws.amazon.com/eks/latest/userguide/pod-id-minimum-sdk.html).

## 4. Inspect evidence, then remove temporary privileged access

Before cleanup, check the sanitized report's migration heads:

| Service | Expected head |
| --- | --- |
| catalog | `0003_event_outbox` |
| booking | `booking_0003` |
| payment | `payment_0001` |
| admission | `admission_0002` |
| analytics | `analytics_0003` |

After successful evidence export:

```powershell
./scripts/bootstrap-cloud-database.ps1 -RemoveCompletedJob
```

Then in the same owner CloudShell session:

```bash
bash "$task_dir/apply-access-cloudshell.sh" --remove-bootstrap
```

Verify that the Job, service account, temporary Role/RoleBinding, IAM role and Pod Identity association are absent. Retain the five runtime Secrets and initialized RDS data. Record cleanup evidence and set `temporary_access_removed: true` only after checking AWS and Kubernetes. The catalog image upload permission remains for subsequent releases. A completed Job alone does not revoke its privileged identity.

## 5. Failure and retry

Failures emit an exception class without SQL parameters or passwords. Check Pod scheduling, sanitized Job logs, Pod Identity association and stack status first. If a database step fails, preserve the prepared secret values; deleting them could orphan an existing login password. The bootstrap is restartable and reuses those values. Export failure evidence and deliberately remove the old Job/release before rerunning; Helm cannot update an existing Job's immutable Pod template.

No API should start until the verification report passes and all runtime secrets are ready. Database credential rotation requires coordinated ALTER ROLE, Secrets Manager and Kubernetes updates; rerunning this bootstrap is not a rotation procedure.

## 6. Costs and retention

The agreed planning allowance remains **USD 75**, with modeled foundation cost approximately **USD 52.41** through cleanup starting **25 October 2026, 6:00 PM Asia/Colombo**, before usage, taxes, deletion duration and retained artifacts. This is not an enforced AWS spending cap or a live bill.

This stage uses the existing capacity. The approximately 94 MB bootstrap image, secret versions/API calls, logs and network transfer add variable charges. Keep image storage within the previously agreed 14-day post-teardown review package; retain Terraform state, take the final database snapshot and use the agreed secret recovery process. No automatic cleanup or billing alert has been scheduled.

## 7. Validation completed before AWS mutation

Local isolated PostgreSQL 16 tests ran the bootstrap twice using a non-superuser administrative role. They checked migration heads, inventory counts, credential reuse, preservation of edits, denial of cross-schema access/DDL/Metabase access, trusted TLS, wrong-host rejection and rejection of an untrusted CA. Three unit/guard tests passed; strict Helm lint, PowerShell syntax and Bash syntax validation passed. AWS IAM Access Analyzer returned no findings for both reviewed identity policies, and CloudFormation template validation accepted the named-IAM template.

One live RDS bootstrap run passed: five expected migration heads, five TLS 1.3 runtime connections, cross-schema/DDL/migration-metadata restrictions, aggregate-only reporting and hostname-mismatch rejection. All eleven post-cleanup checks passed. The verifier inspected secret metadata and Kubernetes field names/lengths without retrieving secret values into Python. RDS remains available and private. The local disposable PostgreSQL test containers/network were removed.

Run post-cleanup metadata verification without recreating privileged access:

```powershell
. ./scripts/aws-common.ps1
$env:PATH = (Split-Path $LocalAws -Parent) + [IO.Path]::PathSeparator + $env:PATH
& ./.venv/Scripts/python.exe scripts/verify_database_bootstrap.py
```

The original Step 10A evidence is a historical foundation-only snapshot. Its `five_empty_service_secret_containers` assertion describes the pre-bootstrap state; those containers now intentionally contain runtime credentials. Use the Step 10B verifier for their initialized state. Database restore and credential-rotation rehearsals remain future work; this bootstrap did not restore a snapshot.

Next: Step 10C deploys service images and independently supervised workers, with separate runtime AWS identities and environment-isolated event transport. Full application functionality and Metabase cloud connection remain pending.
