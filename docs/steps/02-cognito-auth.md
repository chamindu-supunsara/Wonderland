# Step 02 — Cognito signup, login and roles

This lesson connects the Angular app to a real Amazon Cognito user pool and makes Python verify access tokens. The infrastructure and application code are implemented. A real visitor signup/login, visitor admin-page denial, deliberate administrator promotion, fresh administrator login/API verification, signout redirect and session reload were verified on 15 October 2026. Follow the walkthrough below to reproduce them. Automated tests separately use locally signed RSA tokens and mocked SDK responses. A real password recovery walkthrough remains pending.

## 1. Understand the components

```text
Angular signup/login forms ── Amplify Auth (SRP) ── Amazon Cognito in Mumbai
Angular account/admin page ── Bearer access token ── Python Catalog API
Python API ── fixed Cognito JWKS URL ── public signing keys
```

Passwords and verification codes are handled by Cognito through the Amplify SDK. Our Python API never receives passwords. There is no custom password database. The frontend uses the Amplify Auth library; Amplify Hosting is a later deployment step.

| Identity | Allowed now |
|---|---|
| Anonymous | Browse attractions and ticket tiers; signup, confirm email, recover password |
| Visitor | Above plus verified `/api/v1/users/me` and account page |
| Administrator | Above plus `/api/v1/admin/access-check` and administrator page |

Every confirmed signup defaults to **visitor**. Visitors do not need a Cognito group. Only exact membership in **Administrators** grants administrator status. No signup role selector or writable custom role attribute exists. These are application roles, not AWS IAM roles: park administrators cannot administer your AWS account.

## 2. Infrastructure already deployed

Deployment date: 15 October 2026. Region: **ap-south-1** (Mumbai). Stack: **wonderland-dev-auth**.

| Output | Value |
|---|---|
| User pool | `ap-south-1_aBuDlZ9RC` |
| Angular app client | `202ssal4mlube43ttm0j5m3k4i` |
| Administrator group | `Administrators` |
| Issuer | `https://cognito-idp.ap-south-1.amazonaws.com/ap-south-1_aBuDlZ9RC` |

These IDs are public configuration, not access keys. Never put AWS credentials, client secrets, user passwords, or tokens in the Angular config or repository.

The source of truth is `infra/auth/cognito.yaml`. CloudFormation creates:

- A Lite user pool with case-insensitive email sign-in and verified email recovery.
- Self-service signup with a six-digit email confirmation code.
- A minimum 12-character password policy requiring uppercase, lowercase, numbers and symbols.
- A public browser app client **without a client secret**, with SRP and refresh-token flows.
- Five-minute access/ID tokens and a one-day refresh token.
- Token revocation enabled and an initially empty Administrators group.
- Retention and deletion protection on the user pool to protect account data.

Initial assignment authentication uses email verification and a password. MFA is currently off. Before a production release, implement administrator TOTP enrollment/challenges, assess abuse protection and email delivery configuration, and review the token-storage/XSS tradeoffs. An identity pool and IAM credentials are unnecessary for this user-pool-only flow.

To reproduce deployment in another environment, upload `infra/auth/cognito.yaml` through CloudShell Actions → Upload file, then run in CloudShell (bash):

```bash
aws cloudformation validate-template --template-body file://cognito.yaml --region ap-south-1 --no-cli-pager
aws cloudformation deploy --stack-name wonderland-dev-auth --template-file cognito.yaml --region ap-south-1 --parameter-overrides EnvironmentName=dev --no-cli-pager
aws cloudformation describe-stacks --stack-name wonderland-dev-auth --region ap-south-1 --query 'Stacks[0].Outputs' --output json --no-cli-pager
```

Use the same stack to update this environment. Avoid creating a duplicate pool manually. This deployment creates no EKS cluster, database, or IAM role. Later Terraform infrastructure should reference this pool/client or deliberately import/migrate ownership, rather than create another identity system. Review AWS billing and service quotas in your own account as usage grows.

## 3. Connect local applications

Already completed for the IDs above. To reconnect after a deliberate environment change, run in PowerShell from `D:\Courses\Microservices`:

```powershell
.\scripts\connect-cognito.ps1 -Region ap-south-1 -UserPoolId ap-south-1_aBuDlZ9RC -ClientId 202ssal4mlube43ttm0j5m3k4i
```

This preserves existing database settings, updates the ignored `services/catalog/.env`, and writes public IDs to `frontend/public/app-config.json`.

```json
{
  "apiBaseUrl": "/api/v1",
  "cognito": {
    "region": "ap-south-1",
    "userPoolId": "ap-south-1_aBuDlZ9RC",
    "userPoolClientId": "202ssal4mlube43ttm0j5m3k4i"
  }
}
```

The API needs `COGNITO_REGION`, `COGNITO_USER_POOL_ID`, and `COGNITO_APP_CLIENT_ID`. Restart the host API after changing these. For the Docker API:

```powershell
docker compose up -d --build catalog
```

Keep only one API listening on port 8001. Run Angular separately with `scripts/start-frontend.ps1`. Reload the browser after configuration changes. Configuration loads before authentication initializes; missing/invalid Cognito config disables account forms while public browsing remains available. Later, set `apiBaseUrl` to the HTTPS gateway base URL and configure CORS for the deployed Angular origin.

## 4. Create your first visitor account

1. Open **http://127.0.0.1:4200/signup**.
2. Enter your name, an email address you control, and a new password twice. Enter and submit the password yourself in the app; do not send it to an assistant or put it in a shell command.
3. Select **Create account**.
4. Check your email, including spam, for **Verify your Wonderland account**.
5. Enter the six-digit code in the app and select **Verify email**. Use **Resend verification code** if necessary; avoid repeated requests that trigger limits.
6. Sign in with your email and password.
7. The account page must show **Visitor** and **Python API verified: visitor access.** This second message proves the API accepted a real access token.
8. Open `/admin` as this visitor. You should return to the account page with an access-denied explanation. The API independently rejects visitor access with HTTP 403.
9. Refresh the page and verify that the session is restored. Tokens use sessionStorage in the current browser tab. Sign out from the account page and verify `/account` returns to login.

The AWS Console login and the Wonderland login are separate. Being signed in to AWS does not sign you in to Wonderland.

## 5. Grant the administrator role deliberately

First complete visitor signup and verification. Choose the exact account you intend to promote; do not promote all users or add a frontend role switch.

1. Open the Amazon Cognito console and select Mumbai.
2. Open user pool **wonderland-dev-users** (`ap-south-1_aBuDlZ9RC`).
3. Open **Users**, select your intended verified user, and inspect its email/username.
4. In its group membership area, choose **Add user to group** and select **Administrators**. Console labels can vary; the destination is the pool's Administrators membership list.
5. Review that exact user and group before confirming the addition.
6. Sign out of Wonderland and sign in again to obtain a token containing the group.
7. The account page now shows **Administrator**. Follow **Administrator area** or open `/admin`.
8. Confirm **Python API verified: administrator access.**

Alternatively, in your own authenticated CloudShell session, replace the placeholder with the exact Cognito username you have reviewed:

```bash
aws cognito-idp admin-add-user-to-group --user-pool-id ap-south-1_aBuDlZ9RC --username 'EXACT_COGNITO_USERNAME' --group-name Administrators --region ap-south-1
```

To remove that membership, use `admin-remove-user-from-group` with the same reviewed identifiers. Group changes appear in newly issued tokens. The API verifies JWTs offline and does not query group membership per request, so already-issued access tokens can remain usable until their five-minute expiry. Sign-out/revocation also does not immediately invalidate an access token for this offline verifier. Production designs that require immediate denial need an additional revocation/session check.

There is no administrator catalog editor in this lesson. Step 03 will use the verified administrator dependency for real catalog writes.

## 6. Password recovery

1. Sign out and select **Forgot your password?** on `/login`.
2. Enter your verified account email and select **Send reset code**.
3. Enter the code from email, a new password and its confirmation.
4. Select **Update password**, then sign in with the new password.

Codes and passwords stay in the app. Invalid/expired codes display a retry message. To request another reset code, return to login → Forgot your password. Newly invited users with a temporary password are prompted for a permanent password. Other challenge types are not enabled by the current pool template and show an explicit unsupported-step message if the pool configuration changes.

## 7. How the Python protection works

`services/catalog/app/auth.py` validates the RS256 signature using keys from the configured pool, then checks expiry, issue time, issuer, required subject, `token_use=access`, and the exact app `client_id`. An ID token is not accepted as API authorization. It validates group claim shape before checking Administrators. Keys are cached and refreshed by PyJWT; key-service outages fail closed with 503. Invalid/missing credentials return 401; valid visitors on administrator routes receive 403.

```python
from app.auth import CurrentUser, Administrator

# In a route function:
# def own_history(user: CurrentUser): ...
# def edit_attraction(user: Administrator): ...
```

Use verified `user.user_id` (Cognito `sub`) as the owner of future bookings. Do not accept an owner ID from the browser as authority. Ownership storage and filtering will be implemented with Booking in Step 04; account display is not a full domain profile/history system.

Angular guards control navigation; Python dependencies enforce security. The HTTP interceptor attaches the **access token** only to the configured API origin and exact base-path boundary, including when refreshing an expired session. SDK requests to Cognito do not pass through this interceptor. Public reads do not require authentication.

## 8. Files to study in order

1. `infra/auth/cognito.yaml` — repeatable AWS resources and settings.
2. `frontend/public/app-config.json` and `core/runtime-config.ts` — environment configuration.
3. `frontend/src/app/core/auth/auth-service.ts` — Amplify configuration, signup, session, recovery, logout.
4. `frontend/src/app/features/auth/auth-page.ts` / `.html` — form states, validation and errors.
5. `frontend/src/app/core/auth/auth-interceptor.ts` — token attachment boundary.
6. `frontend/src/app/core/auth/auth-guards.ts` / `app.routes.ts` — guarded routes.
7. `services/catalog/app/auth.py` — trusted identity and roles.
8. `services/catalog/app/api/identity.py` — visitor/admin API proof.
9. `frontend/src/app/features/auth/account-page.ts` — visible API verification.
10. Authentication test files — attack cases, session failures, guards and form behavior.

## 9. Verification and evidence

```powershell
.\scripts\verify.ps1
```

Run with PostgreSQL available. Tests use the separate `_test` database. On this Windows sandbox, test-server connections and Vitest temporary-file renames require normal host execution; a sandbox permission failure is not an application test failure.

Record the outcomes of signup, confirmation, visitor API access, denied admin access, administrator API access, signout, and password recovery in `docs/evidence/step02-validation.md`. Keep screenshots free of passwords, codes and tokens. Automated tests cover backend signature/claim failures, role enforcement, SDK session handling, safe redirects, URL boundaries, guards and password form handling. Real email delivery and SRP login require your account walkthrough.

| Symptom | Check |
|---|---|
| Forms say setup unavailable | Valid app-config.json; IDs from same region/pool; reload |
| User pool/client not found | Region, pool ID, client ID; do not substitute an Identity Pool ID |
| Secret hash required | Wrong app client: use our public client without a secret |
| Email not received | Spam, correct email, Cognito delivery quotas; resend once after waiting |
| Unconfirmed account | Use `/confirm` with email and code, or resend there |
| API 401 after login | Same pool/client on frontend and backend; access token, clock, expiry |
| API 403 for intended admin | Exact Administrators group; correct user; sign out/in after promotion |
| API 503 | Backend configuration or JWKS connectivity; inspect local API logs |
| Account page cannot reach API | Docker healthy / host API running; Angular proxy; port 8001 |
| Works in one tab only | sessionStorage is intentionally per tab; sign in in the other tab |

Do not disable JWT validation, hard-code an administrator, paste tokens into chat, or store tokens in evidence to work around errors.

## 10. Resource lifecycle

Stopping Docker stops only local services. Cognito remains in AWS. The template retains the user pool and enables deletion protection; deleting the CloudFormation stack does not automatically erase the pool. Any final cleanup must deliberately account for retained users and resource ownership. Do not remove it while developing later steps.

Official references: [Cognito JWT verification](https://docs.aws.amazon.com/cognito/latest/developerguide/amazon-cognito-user-pools-using-tokens-verifying-a-jwt.html), [Amplify with existing Cognito resources](https://docs.amplify.aws/javascript/build-a-backend/auth/use-existing-cognito-resources/), [Cognito user pool CloudFormation reference](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-cognito-userpool.html), [app client CloudFormation reference](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-cognito-userpoolclient.html).
