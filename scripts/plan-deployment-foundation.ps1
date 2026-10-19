$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'aws-common.ps1')
Set-Location $ProjectRoot
$env:AWS_PROFILE = 'wonderland-feasibility'
$env:AWS_SDK_LOAD_CONFIG = '1'
$identityText = & $LocalAws sts get-caller-identity --profile wonderland-feasibility --output json --no-cli-pager
Assert-NativeSuccess 'Read deployment identity'
$identity = $identityText | ConvertFrom-Json
if ($identity.Account -ne '708919751353' -or $identity.Arn.EndsWith(':root')) { throw 'Wrong account or root identity.' }
if ($identity.Arn -match '^arn:aws:sts::708919751353:assumed-role/([^/]+)/.+$') {
    $operatorArn = & $LocalAws iam get-role --role-name $Matches[1] --profile wonderland-feasibility --query Role.Arn --output text --no-cli-pager
    Assert-NativeSuccess 'Resolve permanent role ARN'
} elseif ($identity.Arn -match '^arn:aws:iam::708919751353:user/.+$') {
    $operatorArn = $identity.Arn
} else { throw 'Cannot resolve a permanent non-root operator principal.' }
$publicAddress = (Invoke-RestMethod 'https://checkip.amazonaws.com').Trim()
if ([Net.IPAddress]::Parse($publicAddress).AddressFamily -ne [Net.Sockets.AddressFamily]::InterNetwork) { throw 'A public IPv4 address is required.' }
$variables = @{
    operator_arn = $operatorArn.Trim()
    operator_cidr = "$publicAddress/32"
    node_count = 2
    database_class = 'db.t4g.small'
    database_deletion_protection = $true
}
if (Test-Path -LiteralPath 'infra/terraform/foundation/terraform.tfvars') { throw 'Review/remove the alternate terraform.tfvars before generating JSON variables.' }
$variables | ConvertTo-Json | Set-Content -LiteralPath 'infra/terraform/foundation/terraform.tfvars.json' -Encoding utf8
$terraformTool = Join-Path $ProjectRoot '.local/tools/terraform/terraform.exe'
$backend = Join-Path $ProjectRoot 'infra/terraform/foundation/backend.hcl.example'
& $terraformTool '-chdir=infra/terraform/foundation' init -reconfigure -input=false -no-color "-backend-config=$backend"
Assert-NativeSuccess 'Initialize foundation state'
$planFile = Join-Path $ProjectRoot '.local/deployment/foundation.tfplan'
$planOutput = & $terraformTool '-chdir=infra/terraform/foundation' plan -input=false -no-color "-out=$planFile" 2>&1
$planExitCode = $LASTEXITCODE
$planOutput | Set-Content -LiteralPath '.local/deployment/foundation-plan.txt' -Encoding utf8
if ($planExitCode -ne 0) { $planOutput; throw 'Create foundation plan failed.' }
$planOutput | Select-String '^Plan:'
$plan = & $terraformTool '-chdir=infra/terraform/foundation' show -json $planFile
Assert-NativeSuccess 'Read foundation plan'
$plan | Set-Content -LiteralPath '.local/deployment/foundation-plan.json' -Encoding utf8
Write-Host 'Foundation plan saved. No infrastructure apply was attempted.'
