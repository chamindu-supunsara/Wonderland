# Step 09 — isolated MOCK cloud feasibility

Follow [the complete guide](../../docs/steps/09-cloud-feasibility.md). This folder is the bounded experiment, not the full application platform. Its CloudFormation stack name is `wonderland-step09-mock` in account `708919751353`, region `ap-south-1`.

Generate `cloudformation.json` from `template.py`; inspect it and create a change set using `scripts/cloud_feasibility.py plan`. Execution is separate and billable. Do not execute until non-root authentication, current account/quotas, the change set and costs are reviewed. Cleanup deletes only the tagged experiment stack, including its ECR probe images.

The experiment uses a one-node EKS managed node group, two FastAPI probe pods, an internal ALB with manually registered instance target, and an HTTP API private VPC-link integration. It exposes only `GET /smoke/health`. The application remains in its existing local mock mode.

Static preparation is not evidence of a successful AWS deployment. See [validation status](../../docs/evidence/step09-validation.md).

Read-only live readiness checks now pass. The next step is [separate deployment access](../../docs/steps/09-deployment-access.md). `operator-policy.json` is the proposed inline policy for WonderlandFeasibility, combined with ReadOnlyAccess; IAM Access Analyzer reports no findings, but no deployment assignment or billable run is assumed. Its networking/ALB permissions are broader within Mumbai, as explained in the guide.

The image has been built and checked locally. To repeat its restricted container check after building:

```powershell
Get-Content -Raw infra/feasibility/check_container.py | docker run --rm -i --network none --read-only --cap-drop ALL --security-opt no-new-privileges --entrypoint python wonderland-step09-probe:local -
```
