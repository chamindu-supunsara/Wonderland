param(
    [Parameter(Mandatory=$true)][string]$ReleaseFolder,
    [ValidateSet('prepare','apply','rollback')][string]$Phase = 'prepare'
)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'aws-common.ps1')
Set-Location $ProjectRoot
$env:AWS_PROFILE = 'wonderland-feasibility'
& $ProjectPython scripts/promote_release.py $ReleaseFolder $Phase
Assert-NativeSuccess "Mock release $Phase"
