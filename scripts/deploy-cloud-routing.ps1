param([switch]$ApplyInfrastructure, [switch]$DeployFrontend)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'aws-common.ps1')
Set-Location $ProjectRoot
$env:AWS_PROFILE = 'wonderland-feasibility'
$terraform = Join-Path $ProjectRoot '.local/tools/terraform/terraform.exe'
$helm = Join-Path $ProjectRoot '.local/tools/helm/windows-amd64/helm.exe'
$kubeconfig = Join-Path $ProjectRoot '.local/deployment/kubeconfig'
$identity = (& $LocalAws sts get-caller-identity --output json --no-cli-pager) | ConvertFrom-Json
Assert-NativeSuccess 'Verify routing deployment operator'
if ($identity.Account -ne '708919751353' -or $identity.Arn -notmatch ':assumed-role/AWSReservedSSO_WonderlandFeasibility_') { throw 'Unexpected deployment identity' }
if (-not $ApplyInfrastructure -and -not $DeployFrontend) { throw 'Choose the reviewed infrastructure or frontend phase' }
if ($ApplyInfrastructure) {
    $review = Get-Content docs/evidence/step10d-routing-plan.json -Raw | ConvertFrom-Json
    if ($review.status -ne 'PLANNED_NOT_APPLIED') { throw 'Prepare a fresh review before changing infrastructure' }
    if ((Get-FileHash .local/deployment/step10d-routing.tfplan -Algorithm SHA256).Hash.ToLowerInvariant() -ne $review.plan_sha256) { throw 'Reviewed plan changed' }
    foreach ($file in $review.sources_sha256.PSObject.Properties) {
        if ((Get-FileHash $file.Name -Algorithm SHA256).Hash.ToLowerInvariant() -ne $file.Value) { throw "Reviewed source changed: $($file.Name)" }
    }
    & $terraform '-chdir=infra/terraform/routing' apply '-input=false' '-no-color' '../../../.local/deployment/step10d-routing.tfplan'
    Assert-NativeSuccess 'Apply only reviewed routing and frontend resources'
    & $terraform '-chdir=infra/terraform/routing' output '-json' | Set-Content .local/deployment/routing-outputs.json -Encoding utf8
    Assert-NativeSuccess 'Export public routing metadata'
}
if (-not $DeployFrontend) { return }
$outputs = Get-Content .local/deployment/routing-outputs.json -Raw | ConvertFrom-Json
& $helm upgrade --install aws-load-balancer-controller eks/aws-load-balancer-controller --version 3.6.0 --namespace kube-system --kubeconfig $kubeconfig -f deploy/controller-values.yaml --wait --timeout 600s
Assert-NativeSuccess 'Install pinned target registration controller'
$bindings = @{vpcId='vpc-00967ab06f35249ff'; targetGroups=$outputs.target_groups.value}
$bindings | ConvertTo-Json -Depth 10 | Set-Content .local/deployment/routing-bindings.json -Encoding utf8
& $helm upgrade --install wonderland-routing deploy/helm/routing --namespace wonderland --kubeconfig $kubeconfig -f .local/deployment/routing-bindings.json --wait --timeout 120s
Assert-NativeSuccess 'Bind existing private API Pods to reviewed target groups'
$values = Get-Content .local/deployment/workload-values.json -Raw | ConvertFrom-Json
if ($values.pricingMode -ne 'projection') { throw 'Verified pricing projection is required' }
$values.frontendOrigin = $outputs.frontend_origin.value
$values | ConvertTo-Json -Depth 12 | Set-Content .local/deployment/workload-values.json -Encoding utf8
& $helm upgrade wonderland deploy/helm/wonderland --namespace wonderland --kubeconfig $kubeconfig -f .local/deployment/workload-values.json --wait --timeout 600s
Assert-NativeSuccess 'Roll out exact hosted frontend origin while retaining mock configuration'
& ./.venv/Scripts/python.exe scripts/wait_routing_targets.py
Assert-NativeSuccess 'Wait for all four private target groups to be healthy'
Push-Location frontend
try {
    & npm.cmd run build
    Assert-NativeSuccess 'Build production Angular bundle'
} finally { Pop-Location }
& ./.venv/Scripts/python.exe scripts/publish_frontend.py
Assert-NativeSuccess 'Publish versioned Angular artifact through Amplify manual deployment'
& ./.venv/Scripts/python.exe scripts/verify_public_routing.py
Assert-NativeSuccess 'Verify hosted SPA, routing, CORS and unauthenticated denials'
