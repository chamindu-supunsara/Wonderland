. "$PSScriptRoot\aws-common.ps1"
# AWS prompts for the access portal URL, Identity Center region, account and permission set.
# Password/MFA entry belongs in the official browser flow, never in this script.
& $LocalAws configure sso --profile wonderland-worker-source
Assert-NativeSuccess 'IAM Identity Center temporary login setup'
