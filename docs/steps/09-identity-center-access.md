# Step 09 — first Identity Center user and read-only CLI access

Confirmed by the user: AWS account `708919751353` appears under Identity Center's AWS accounts. Portal: `https://d-9f675820da.awsapps.com/start`. Identity Center and deployment region: `ap-south-1`.

The screenshot and account list confirm portal configuration and account visibility. They do not prove a user, permission set, assignment or working CLI session exists. This walkthrough starts with read-only account discovery; EKS provisioning permissions are a separate step.

## 1. Create your user in Identity Center

Use the current account-owner/administrator console in Mumbai. Open **IAM Identity Center**, rather than the ordinary IAM Users page.

1. Choose **Users → Add user**.
2. Username: `chamindu` (or reuse your existing Identity Center user if already created).
3. Password: **Send an email to this user with password setup instructions**.
4. Enter your own email address twice and your first/last name.
5. Choose **Next**, skip group membership for this first personal assignment, review and **Add user**.

In your email, open the AWS invitation and set your password directly on AWS. Never send the password or invitation token to this chat. If the invitation is missing, check spam or use the user's **Resend invitation** action when available. A Cognito Wonderland application user is a separate identity and does not automatically become this user.

## 2. Create the permission set

1. Open **Multi-account permissions → Permission sets → Create permission set**.
2. Choose **Predefined permission set** and the AWS managed policy **ReadOnlyAccess**.
3. Set **Permission set name** to exactly `WonderlandReadOnly`.
4. Set **Session duration** to **1 hour**. Leave relay state empty.
5. Review and create.

ReadOnlyAccess allows broad account inventory reads; it is not a booking visitor role and is not a deployment policy. Some APIs can still be denied by organizational controls or other restrictions. Do not select AdministratorAccess or PowerUserAccess for this discovery profile. Temporary CLI SSO access does not require long-lived access keys or SignInLocalDevelopmentAccess.

## 3. Assign the user to your account

1. Open **AWS accounts**, select `708919751353`, then **Assign users or groups**.
2. Choose **Users**, select `chamindu` (or your chosen existing user), then **Next**.
3. Select `WonderlandReadOnly`, choose **Next**, review the account/user/permission set, then **Submit**.
4. Wait for successful provisioning. Merely creating the permission set does not grant the user account access.

For a larger team, assign a group instead. This walkthrough uses a direct assignment for your one personal user.

## 4. Enable MFA and test the portal

Configure Identity Center MFA from **Settings → Authentication → Multi-factor authentication**, using the current console's Configure action. Require MFA for users who can register a device; configure device registration so your new user can enroll. Register your authenticator/passkey directly with AWS when prompted. Keep recovery details private. Follow the [AWS MFA guide](https://docs.aws.amazon.com/singlesignon/latest/userguide/mfa-configure.html) for the exact available options.

Open the portal in a private browser window:

https://d-9f675820da.awsapps.com/start

Sign in with your Identity Center username/password, complete MFA and expand account `708919751353`. You should see `WonderlandReadOnly`. Clicking that permission set opens the AWS Console with that role. If no account appears, verify the assignment completed and sign out/in again. Continue to keep the owner setup session available until the new user's access works.

## 5. Connect the prepared project CLI profile

The public configuration has been prepared in ignored `.local/aws/config` under a new profile `wonderland-readonly`. Existing root/worker profiles have not been changed. This prevents the old root login session from being reused accidentally.

To recreate the configuration if needed:

```powershell
& .\.venv\Scripts\python.exe scripts/prepare_cloud_sso.py
```

In PowerShell at `D:\Courses\Microservices`:

```powershell
. .\scripts\aws-common.ps1
& $LocalAws sso login --profile wonderland-readonly
```

The CLI opens the official AWS browser authorization flow. Use the new Identity Center user, complete MFA and approve the CLI request directly in AWS. This is `sso login`, not the root-oriented `aws login` used earlier.

Verify:

```powershell
& $LocalAws sts get-caller-identity --profile wonderland-readonly
```

Expected account: `708919751353`. Expected ARN pattern: `arn:aws:sts::708919751353:assumed-role/AWSReservedSSO_WonderlandReadOnly_.../...`. It must not end in `:root`. A missing `WonderlandReadOnly` role usually means the permission set name or assignment differs from this guide.

## 6. Continue the account readiness check

```powershell
& .\.venv\Scripts\python.exe scripts/cloud_feasibility.py check --profile wonderland-readonly
```

The explicit profile matters: the lifecycle tool's existing default still points to the old worker-source profile. The check records actual resource/quota results in `.local/feasibility/account-check.json`; individual denials stay UNVERIFIED. We will review those results before preparing a separate deployment permission set. This profile cannot deploy EKS or assume that deployment is approved.

Because you previously reported remaining Free Tier credits, recheck Billing after organization creation and before provisioning any billable infrastructure. AWS states that organization creation can expire Free Tier credits and upgrade a Free plan. No EKS deployment, budget approval or current credit balance is implied by completing Identity Center setup.

Official references: [user and account assignment workflow](https://docs.aws.amazon.com/singlesignon/latest/userguide/quick-start-default-idc.html), [CLI SSO configuration](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sso.html), [organization setup and billing consequence](https://docs.aws.amazon.com/singlesignon/latest/userguide/enable-identity-center.html).
