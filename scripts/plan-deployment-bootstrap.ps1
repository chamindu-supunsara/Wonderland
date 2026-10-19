param([string]$Profile = 'wonderland-feasibility')
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'aws-common.ps1')
$repoRoot = Split-Path $PSScriptRoot -Parent
Set-Location $repoRoot
$identityText = & $LocalAws sts get-caller-identity --profile $Profile --output json --no-cli-pager
if ($LASTEXITCODE -ne 0) { throw 'Renew your non-root SSO login before planning.' }
$identity = $identityText | ConvertFrom-Json
if ($identity.Account -ne '708919751353' -or $identity.Arn.EndsWith(':root')) {
    throw 'Use a non-root identity in account 708919751353.'
}
$env:AWS_PROFILE = $Profile
$env:AWS_SDK_LOAD_CONFIG = '1'
$planDirectory = Join-Path $repoRoot '.local/deployment'
New-Item -ItemType Directory -Force -Path $planDirectory | Out-Null
$planFile = Join-Path $planDirectory 'bootstrap.tfplan'
$terraformTool = Join-Path $repoRoot '.local/tools/terraform/terraform.exe'
& $terraformTool '-chdir=infra/terraform/bootstrap' plan -input=false -no-color "-out=$planFile"
if ($LASTEXITCODE -ne 0) { throw 'Bootstrap plan failed. No apply was attempted.' }
$planText = & $terraformTool '-chdir=infra/terraform/bootstrap' show -json $planFile
if ($LASTEXITCODE -ne 0) { throw 'Could not read the saved plan.' }
$planText | Set-Content -LiteralPath (Join-Path $planDirectory 'bootstrap-plan.json') -Encoding utf8
Write-Host "Saved reviewable plan: $planFile. This script never applies infrastructure."
