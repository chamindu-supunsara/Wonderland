# Step 11 — tested mock releases and controlled deployment

Status: implementation prepared; real GitHub checks, OIDC release and promotion evidence are required before completion. Checkout, Admission and Analytics stay mock.

## 1. Pipeline and access boundaries

Repository: https://github.com/chamindu-supunsara/Wonderland. Pull requests and main pushes run Python lint/format, PostgreSQL integration tests, Angular tests/build, Helm rendering tests and Terraform validation. These checks have no AWS role. Actions are pinned to immutable commits. Raw cloud evidence, state, local configuration and credentials are excluded from the public repository. The public RDS CA bundle is intentionally included for image builds.

The manually dispatched **Mock release** workflow repeats the checks for its exact main commit, builds five Linux/amd64 service images, uploads them to the existing ECR repositories and saves an immutable GitHub artifact containing `manifest.json` and `frontend.zip`. The manifest records commit, run/attempt, image digests, frontend checksum and approved chart/migration fingerprints. Artifacts expire after seven days; retain the local known-good release and existing images for the agreed recovery period.

GitHub OIDC grants temporary AWS credentials through `wonderland-github-release`. Trust matches exactly `repo:chamindu-supunsara/Wonderland:ref:refs/heads/main` and audience `sts.amazonaws.com`. The role can authenticate to ECR and publish only to the five named existing repositories. It cannot read secrets, deploy to EKS, apply Terraform, create repositories or change the frontend. No static AWS access key belongs in GitHub secrets. See [GitHub's AWS OIDC guide](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws).

The final promotion runs on your existing Windows computer using temporary WonderlandFeasibility SSO and the existing EKS operator `/32`. This keeps the cluster API restricted and avoids another runner host or broad GitHub runner IP ranges. No persistent self-hosted GitHub runner is installed. This is automated CI/build with an explicit operator-controlled delivery stage; it is not unattended deployment on every push.

## 2. Costs and cleanup

The previous USD 64.41 model plus USD 1 image-storage reserve gives **USD 65.41 before exclusions**, within the USD 75 allowance. No extra EC2, RDS, NAT or ALB is created. Public repository standard hosted runners currently have free usage; check current GitHub account terms before switching visibility or runner types. AWS storage, transfer, taxes and retained artifacts still vary. The delayed 18 October account estimate was USD 4.16 at preparation; it is not the current or final bill.

Keep cleanup on **25 October 2026, 6 PM Asia/Colombo**. Promotion refuses after that deadline. Preserve state, database snapshot, encryption key and known-good images/archives through the agreed **8 November, 6 PM** recovery review. Delete the OIDC role/stack at teardown if no further publishing is needed; first check whether the provider is shared before removing it. Never delete images needed for recovery.

## 3. One-time owner setup

Review `infra/automation/github-release-access.json`, the least-privilege policy and the local evidence receipt `docs/evidence/step11-access-review.json`. The approved owner bundle is `.local/deployment/step11-automation-access.zip`. In owner CloudShell, verify its SHA256, extract into a dedicated folder, then run:

```bash
bash apply-access-cloudshell.sh --prepare
bash apply-access-cloudshell.sh --apply
```

Preparation validates the template and prints Access Analyzer findings; inspect them before applying. The helper verifies account 708919751353 and the exact template hash. If an OIDC provider already exists, it stops for an explicit reuse review. Do not use the developer role to grant itself access. This setup creates only the provider and named publishing role.

## 4. Daily development and CI

Create a feature branch, edit code, run `./scripts/verify.ps1`, commit and push. Open a pull request to main and inspect **Milestone checks**. Fix failures before merging. Helm tests work from a clean Linux checkout, and policy tests reconstruct their baseline from checked-in declarations rather than an ignored developer file. Terraform validation uses `-backend=false` and never plans/applies cloud resources in CI.

Do not use `pull_request_target` to run contributed code with AWS permissions. OIDC publishing is a separate manual main-only workflow. Repository administrators must protect main and review changes to workflows, automation, IAM policies and the release contract. GitHub plan capabilities can affect branch protection; verify applied settings rather than assuming they exist.

## 5. Build an exact mock release

1. Open GitHub → Actions → **Mock release** → **Run workflow**, branch **main**.
2. Wait for all check jobs and the publish job to succeed.
3. Open the run. Record the source commit and numeric run ID from its URL.
4. The artifact is `mock-release-<run ID>-<attempt>`; five ECR tags contain commit/run/attempt, and the manifest uses digests. A retry uses a different attempt and does not overwrite immutable tags.

Local Git Credential Manager supplies existing GitHub authentication for downloading and dispatching; credentials are held in memory and never printed or saved by our scripts. Password/MFA entry stays in GitHub's own login UI.

## 6. Download, review and promote

From the workspace, with the exact released commit checked out and no tracked edits:

```powershell
. ./scripts/aws-common.ps1
& $LocalAws sso login --profile wonderland-feasibility
& ./.venv/Scripts/python.exe scripts/download_release.py <RUN_ID>
./scripts/promote-release.ps1 -ReleaseFolder .local/releases/<RUN_ID>-<ATTEMPT> -Phase prepare
```

The downloader verifies the successful manual workflow, repository, main branch, source/run/attempt, GitHub artifact SHA256 and exact archive entries. It does not forward the GitHub credential to signed blob storage or print signed URLs.

Preparation validates the manifest, exact source commit, frontend/Cognito target, image repositories/digests, unchanged approved charts/migrations, live mock flags, projection pricing, Helm baseline, two Ready nodes and Pod slots. It saves current Helm values and a known-good frontend archive for rollback, then renders the proposed chart and rejects added Secrets/Ingress/Jobs or replica/resource changes. Read the generated `review.json`; it has no passwords.

Only after reviewing that concrete release:

```powershell
./scripts/promote-release.ps1 -ReleaseFolder .local/releases/<RUN_ID>-<ATTEMPT> -Phase apply
```

The runner checks review hashes, live revision/configuration and a 30-minute preparation limit, then upgrades the existing Helm release with rollback-on-failure and publishes the already-built frontend archive through Amplify. It performs private API readiness, all API/worker image/readiness checks, hosted exact frontend/config checks, public browsing and authentication denials, node count and private BI checks. No credentials are read from Kubernetes Secrets. A receipt is written only after those checks pass. No migrations, seed reset, IAM bootstrap, Terraform apply or infrastructure scale-up runs during normal promotion.

Chart or database migration changes intentionally stop at this boundary. Review backward compatibility, migration/restore strategy, capacity and costs separately; do not bypass the protected fingerprint contract to make a rollout pass.

## 7. Failure handling and rollback

If Helm fails, its rollback-on-failure restores the preceding successful Helm revision. Inspect Pods/events and sanitized application logs; do not print Secret YAML, database URLs or tokens. If frontend publication or a post-deploy check fails after backend success, treat the deployment as partial and inspect before retrying. Kubernetes and Amplify do not form one atomic transaction.

To explicitly restore the reviewed prior values and frontend archive after a completed/partial promotion:

```powershell
./scripts/promote-release.ps1 -ReleaseFolder .local/releases/<RUN_ID>-<ATTEMPT> -Phase rollback
```

Rollback refuses if live images changed again. It restores the saved frontend and Helm images/configuration and reruns the same checks. This is application rollback, not database rollback; database schema changes are excluded from this path. Keep both the deployment and rollback receipts. Do not force an older artifact onto a later unrelated rollout.

## 8. Required evidence and remaining scope

Record repository URL, source commit, hosted check/run links, OIDC role/trust, digest manifest, prepared review, deployment and verification outcomes, elapsed time and rollback evidence. Keep sanitized summaries in the repository and raw operator/guest evidence locally. A prepared YAML file alone is not proof of a passing hosted pipeline.

Step 12A provider sandbox and remaining features, Step 12B measured reliability/scaling/restore checks and Step 12C submission/viva remain separate milestones. This automation keeps payment mock and does not make those requirements complete.
