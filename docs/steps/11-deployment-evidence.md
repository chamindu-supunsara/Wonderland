# Step 11 — execution summary

Completed 19 October 2026 for the approved mock-delivery scope.

- [Repository](https://github.com/chamindu-supunsara/Wonderland)
- [Successful OIDC release](https://github.com/chamindu-supunsara/Wonderland/actions/runs/39210950664)
- Released source: `88ee70c6cc93a468c9fb248d9f3f3dd54507fd64`.
- Hosted checks: **212 Python tests**, zero failures/errors/skips; Angular checks/build and all five Terraform validations passed.
- Artifact SHA256: `78af15f446ea3122643f09aae43c319a9feb737af9df968dc213ab6aa4488974`.
- Five images were built by GitHub and published by digest through the main-only OIDC role; no long-lived AWS key was stored in GitHub.
- Seven live access checks verified exact immutable subject/audience, provider, policy and one-hour session duration.
- Deployment, application rollback and final re-deployment each passed **23 checks**. Final state: Helm revision **8**, Amplify job **6**, same two EKS nodes, private Metabase.
- All payment/admission/analytics flags stayed mock. Database schema, replicas, resource limits and infrastructure size stayed unchanged during promotion.
- Before/after facts reconciled: two simulated purchases, USD 80 mock revenue, one guest arrival and two ride uses. Database TLS and both worker pollers passed.

Owner CloudShell's trust correction returned:

```text
Successfully created/updated stack - wonderland-github-release-access
STEP11_EXIT=0
```

The live trust uses `repo:chamindu-supunsara@80322623/Wonderland@1425166882:ref:refs/heads/main`, audience `sts.amazonaws.com`. The initial legacy-subject failure and a later incorrect auth-probe URL were diagnosed and corrected; their local evidence is retained. A regression test binds probes to real protected routes.

Delivery is GitHub CI/build/publication plus an explicit operator SSO-controlled promotion. Main requires checks and blocks force pushes/deletion, with an administrator bypass. This does not claim unattended EKS deployment, database restore, real payment integration, fault-injection resilience or completed assignment submission.

Planning model remains USD 65.41 before exclusions within the USD 75 allowance; it is not a verified bill or an enforced cap. Cleanup remains 25 October 2026 at 6 PM Asia/Colombo, with recovery material review on 8 November at 6 PM. See the [full guide](11-deployment-automation.md) for commands, boundaries and recovery.
