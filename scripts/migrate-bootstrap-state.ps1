$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'aws-common.ps1')
Set-Location $ProjectRoot
$env:AWS_PROFILE = 'wonderland-feasibility'
$env:AWS_SDK_LOAD_CONFIG = '1'
$identityText = & $LocalAws sts get-caller-identity --profile wonderland-feasibility --output json --no-cli-pager
Assert-NativeSuccess 'Read non-root identity'
$identity = $identityText | ConvertFrom-Json
if ($identity.Account -ne '708919751353' -or $identity.Arn.EndsWith(':root')) { throw 'Wrong account or root identity.' }
$source = Join-Path $ProjectRoot 'infra/terraform/bootstrap/backend.tf.example'
$target = Join-Path $ProjectRoot 'infra/terraform/bootstrap/backend.tf'
if ((Test-Path -LiteralPath $target) -and (Get-Content -Raw -LiteralPath $target) -ne (Get-Content -Raw -LiteralPath $source)) {
    throw 'Existing bootstrap backend differs; review it before migrating.'
}
Copy-Item -LiteralPath $source -Destination $target
$backend = Join-Path $ProjectRoot 'infra/terraform/bootstrap/backend.hcl.example'
& (Join-Path $ProjectRoot '.local/tools/terraform/terraform.exe') '-chdir=infra/terraform/bootstrap' init -migrate-state -force-copy -input=false -no-color "-backend-config=$backend"
Assert-NativeSuccess 'Copy bootstrap state to the approved protected bucket'
Write-Host 'Bootstrap state now uses S3 versioning and lock files. Keep the local backup secure.'
