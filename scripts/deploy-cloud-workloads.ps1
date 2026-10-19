param([switch]$ApplyInfrastructure, [switch]$Deploy)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'aws-common.ps1')
Set-Location $ProjectRoot
$env:AWS_PROFILE = 'wonderland-feasibility'
$env:PATH = (Split-Path $LocalAws -Parent) + [IO.Path]::PathSeparator + $env:PATH
$terraform = Join-Path $ProjectRoot '.local/tools/terraform/terraform.exe'
$helm = Join-Path $ProjectRoot '.local/tools/helm/windows-amd64/helm.exe'
$kubectl = Join-Path $ProjectRoot '.local/tools/kubectl.exe'
$kubeconfig = Join-Path $ProjectRoot '.local/deployment/kubeconfig'
$identity = (& $LocalAws sts get-caller-identity --output json --no-cli-pager) | ConvertFrom-Json
Assert-NativeSuccess 'Verify deployment operator'
if ($identity.Account -ne '708919751353' -or $identity.Arn -notmatch ':assumed-role/AWSReservedSSO_WonderlandFeasibility_') { throw 'Unexpected deployment identity.' }
if (-not $ApplyInfrastructure -and -not $Deploy) { throw 'Choose the reviewed -ApplyInfrastructure or -Deploy phase.' }
if ($ApplyInfrastructure) {
    $review = Get-Content docs/evidence/step10c-workloads-plan.json -Raw | ConvertFrom-Json
    if ($review.status -ne 'PLANNED_NOT_APPLIED') { throw 'Refresh and pass live Kubernetes capacity review before workload apply.' }
    $planPath = '.local/deployment/step10c-workloads.tfplan'
    if ((Get-FileHash -LiteralPath $planPath -Algorithm SHA256).Hash.ToLowerInvariant() -ne $review.plan_sha256) { throw 'Reviewed plan checksum changed.' }
    foreach ($file in $review.terraform_sources_sha256.PSObject.Properties) {
        if ((Get-FileHash -LiteralPath $file.Name -Algorithm SHA256).Hash.ToLowerInvariant() -ne $file.Value) { throw "Reviewed Terraform source changed: $($file.Name)" }
    }
    & $terraform '-chdir=infra/terraform/workloads' apply -input=false -no-color '../../../.local/deployment/step10c-workloads.tfplan'
    Assert-NativeSuccess 'Apply exactly the reviewed workloads plan'
    & $terraform '-chdir=infra/terraform/workloads' output -json | Set-Content .local/deployment/workload-outputs.json -Encoding utf8
    Assert-NativeSuccess 'Export nonsecret workloads outputs'
}
if (-not $Deploy) { return }
$outputs = Get-Content .local/deployment/workload-outputs.json -Raw | ConvertFrom-Json
$images = @{}
$dockerConfig = Join-Path $ProjectRoot '.local/deployment/workloads-docker-auth'
New-Item -ItemType Directory -Path $dockerConfig -Force | Out-Null
try {
    $token = & $LocalAws ecr get-login-password --region ap-south-1
    Assert-NativeSuccess 'Get temporary registry authentication'
    $token | & docker --config $dockerConfig login --username AWS --password-stdin 708919751353.dkr.ecr.ap-south-1.amazonaws.com
    Assert-NativeSuccess 'Authenticate Docker to ECR'
    $token = $null
    foreach ($service in @('catalog','booking','payment','admission','analytics')) {
        $localTag = "wonderland-${service}:step10c"
        & docker build --platform linux/amd64 --file "services/$service/Dockerfile" --tag $localTag .
        Assert-NativeSuccess "Build $service"
        $imageId = (& docker image inspect $localTag --format '{{.Id}}').Trim()
        Assert-NativeSuccess "Inspect $service image"
        $tag = 'step10c-' + $imageId.Substring(7,16)
        $repository = "708919751353.dkr.ecr.ap-south-1.amazonaws.com/wonderland-demo/$service"
        & docker tag $localTag "${repository}:$tag"
        Assert-NativeSuccess "Tag $service image"
        $digest = & $LocalAws ecr describe-images --repository-name "wonderland-demo/$service" --image-ids "imageTag=$tag" --query 'imageDetails[0].imageDigest' --output text --no-cli-pager 2>$null
        if ($LASTEXITCODE -ne 0) {
            & docker --config $dockerConfig push "${repository}:$tag"
            Assert-NativeSuccess "Push $service image"
            $digest = & $LocalAws ecr describe-images --repository-name "wonderland-demo/$service" --image-ids "imageTag=$tag" --query 'imageDetails[0].imageDigest' --output text --no-cli-pager
            Assert-NativeSuccess "Resolve $service digest"
        }
        $digest = "$digest".Trim()
        if ($digest -notmatch '^sha256:[a-f0-9]{64}$') { throw "Invalid $service digest" }
        $images[$service] = "$repository@$digest"
    }
} finally {
    $token = $null
    $authFile = Join-Path $dockerConfig 'config.json'
    if (Test-Path -LiteralPath $authFile) { Remove-Item -LiteralPath $authFile -Force }
}
$workers = @{}
foreach ($service in @('catalog','booking','admission')) {
    $workers["$service-publisher"] = @{enabled=$true; env=@{EVENTS_TOPIC_ARN=$outputs.topics.value.$service}}
}
$workers['booking-maintenance'] = @{enabled=$true}
$workers['booking-prices'] = @{enabled=$true; env=@{PRICING_QUEUE_URL=$outputs.queues.value.'booking-prices'}}
$workers['analytics-bookings'] = @{enabled=$true; env=@{BOOKING_QUEUE_URL=$outputs.queues.value.'analytics-bookings'}}
$workers['analytics-admissions'] = @{enabled=$true; env=@{ADMISSION_QUEUE_URL=$outputs.queues.value.'analytics-admissions'}}
$values = @{enabled=$true; frontendOrigin=''; pricingMode='http'; apiReplicas=2; images=$images; workers=$workers}
$valuesPath = '.local/deployment/workload-values.json'
$values | ConvertTo-Json -Depth 12 | Set-Content $valuesPath -Encoding utf8
& $helm lint deploy/helm/wonderland --strict -f $valuesPath
Assert-NativeSuccess 'Validate private mock rollout values'
& $helm upgrade --install wonderland deploy/helm/wonderland --namespace wonderland --kubeconfig $kubeconfig -f $valuesPath --wait --timeout 600s
Assert-NativeSuccess 'Roll out APIs and independently supervised event workers'
& $kubectl --kubeconfig $kubeconfig -n wonderland exec deployment/wonderland-catalog -- python -m app.event_worker snapshot
Assert-NativeSuccess 'Queue current pricing snapshots transactionally'
& ./.venv/Scripts/python.exe scripts/run_workload_smoke.py
Assert-NativeSuccess 'Verify live pricing delivery, health and duplicate protection'
$values.pricingMode = 'projection'
$values | ConvertTo-Json -Depth 12 | Set-Content $valuesPath -Encoding utf8
& $helm upgrade wonderland deploy/helm/wonderland --namespace wonderland --kubeconfig $kubeconfig -f $valuesPath --wait --timeout 600s
Assert-NativeSuccess 'Switch Booking to verified pricing projection'
& ./.venv/Scripts/python.exe scripts/run_workload_smoke.py
Assert-NativeSuccess 'Verify final projection-mode rollout'
Write-Host 'Mock private workload rollout verified. Public routing/frontend and hosted user walkthrough remain Step10D/10E.'
