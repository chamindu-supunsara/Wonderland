$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'aws-common.ps1')
Set-Location $ProjectRoot
$env:AWS_PROFILE='wonderland-feasibility'
Write-Host 'Private cloud Metabase: http://127.0.0.1:3001. Keep this terminal running. Ctrl+C closes the tunnel.'
& ./.local/tools/kubectl.exe --kubeconfig .local/deployment/kubeconfig -n wonderland port-forward --address 127.0.0.1 service/wonderland-metabase 3001:3000
