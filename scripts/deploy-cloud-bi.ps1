param([switch]$ApplySecrets,[switch]$Bootstrap,[switch]$Deploy,[switch]$RemoveBootstrap)
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'aws-common.ps1')
Set-Location $ProjectRoot
$env:AWS_PROFILE='wonderland-feasibility'
$helm=Join-Path $ProjectRoot '.local/tools/helm/windows-amd64/helm.exe'
$kubectl=Join-Path $ProjectRoot '.local/tools/kubectl.exe'
$terraform=Join-Path $ProjectRoot '.local/tools/terraform/terraform.exe'
$kubeconfig=Join-Path $ProjectRoot '.local/deployment/kubeconfig'
$identity=(& $LocalAws sts get-caller-identity --output json)|ConvertFrom-Json
Assert-NativeSuccess 'Verify BI operator'
if ($identity.Account -ne '708919751353' -or $identity.Arn -notmatch ':assumed-role/AWSReservedSSO_WonderlandFeasibility_') {throw 'Unexpected operator'}
if (-not ($ApplySecrets -or $Bootstrap -or $Deploy -or $RemoveBootstrap)) {throw 'Choose one reviewed BI phase'}
if ($RemoveBootstrap) {
    $report=Get-Content docs/evidence/step10e-database-verification.json -Raw|ConvertFrom-Json
    if ($report.status -ne 'VERIFIED') {throw 'Verified bootstrap report required before removal'}
    & $helm uninstall wonderland-bi-bootstrap --namespace wonderland-bootstrap --kubeconfig $kubeconfig --wait --timeout 120s
    Assert-NativeSuccess 'Remove temporary bootstrap Job, ServiceAccount and secret-writer RBAC'
    return
}
$code=Get-Content docs/evidence/step10e-code-review.json -Raw|ConvertFrom-Json
foreach ($item in $code.sources_sha256.PSObject.Properties) {
    if ((Get-FileHash -LiteralPath $item.Name -Algorithm SHA256).Hash.ToLowerInvariant() -ne $item.Value) {throw "Reviewed source changed: $($item.Name)"}
}
if ($ApplySecrets) {
    $plan=Get-Content docs/evidence/step10e-bi-plan.json -Raw|ConvertFrom-Json
    if ($plan.status -ne 'PLANNED_NOT_APPLIED') {throw 'Prepare a fresh plan for future changes'}
    if ((Get-FileHash .local/deployment/step10e-analytics.tfplan -Algorithm SHA256).Hash.ToLowerInvariant() -ne $plan.plan_sha256) {throw 'Plan changed'}
    & $terraform '-chdir=infra/terraform/analytics' apply '-input=false' '-no-color' '../../../.local/deployment/step10e-analytics.tfplan'
    Assert-NativeSuccess 'Apply only the two reviewed BI credential containers'
    & $terraform '-chdir=infra/terraform/analytics' output '-json' |Set-Content .local/deployment/bi-outputs.json -Encoding utf8
    Assert-NativeSuccess 'Export BI container metadata only'
    return
}
if ($Bootstrap) {
    $status=(& $LocalAws cloudformation describe-stacks --stack-name wonderland-bi-bootstrap-access --query 'Stacks[0].StackStatus' --output text).Trim()
    Assert-NativeSuccess 'Verify owner-created temporary bootstrap identity'
    if ($status -notin @('CREATE_COMPLETE','UPDATE_COMPLETE')) {throw 'Temporary bootstrap access not ready'}
    $images=@{}
    $auth=Join-Path $ProjectRoot '.local/deployment/bi-docker-auth'
    New-Item -ItemType Directory -Path $auth -Force|Out-Null
    try {
        $token=& $LocalAws ecr get-login-password --region ap-south-1
        Assert-NativeSuccess 'Get temporary ECR authentication'
        $token| & docker --config $auth login --username AWS --password-stdin 708919751353.dkr.ecr.ap-south-1.amazonaws.com
        Assert-NativeSuccess 'Authenticate registry upload'
        $token=$null
        foreach ($name in @('bootstrap','analytics')) {
            $localTag=if ($name -eq 'bootstrap') {'wonderland-bi-bootstrap:step10e'} else {'wonderland-analytics:step10e'}
            $imageId=(& docker image inspect $localTag --format '{{.Id}}').Trim()
            Assert-NativeSuccess 'Inspect reviewed image'
            if ($imageId -ne $code.images.$name) {throw 'Local image differs from review'}
            $tag='step10e-'+$name+'-'+$imageId.Substring(7,16)
            $repository='708919751353.dkr.ecr.ap-south-1.amazonaws.com/wonderland-demo/analytics'
            & docker tag $localTag "${repository}:$tag"
            Assert-NativeSuccess 'Tag reviewed image'
            $digest=& $LocalAws ecr describe-images --repository-name wonderland-demo/analytics --image-ids "imageTag=$tag" --query 'imageDetails[0].imageDigest' --output text 2>$null
            if ($LASTEXITCODE -ne 0) {
                & docker --config $auth push "${repository}:$tag"
                Assert-NativeSuccess 'Upload immutable image'
                $digest=& $LocalAws ecr describe-images --repository-name wonderland-demo/analytics --image-ids "imageTag=$tag" --query 'imageDetails[0].imageDigest' --output text
                Assert-NativeSuccess 'Resolve ECR digest'
            }
            $digest="$digest".Trim()
            if ($digest -notmatch '^sha256:[a-f0-9]{64}$') {throw 'Invalid image digest'}
            $images[$name]="$repository@$digest"
        }
    } finally {
        $token=$null
        $authFile=Join-Path $auth 'config.json'
        if (Test-Path -LiteralPath $authFile) {Remove-Item -LiteralPath $authFile -Force}
    }
    $images|ConvertTo-Json|Set-Content .local/deployment/bi-images.json -Encoding utf8
    & $kubectl --kubeconfig $kubeconfig -n wonderland get secret wonderland-metabase-app -o name 2>$null
    if ($LASTEXITCODE -ne 0) {
        & $kubectl --kubeconfig $kubeconfig -n wonderland create secret generic wonderland-metabase-app
        Assert-NativeSuccess 'Precreate the single metadata runtime secret'
    }
    & $kubectl --kubeconfig $kubeconfig create configmap wonderland-rds-ca -n wonderland --from-file=deploy/certs/rds-global-bundle.pem --dry-run=client -o yaml | & $kubectl --kubeconfig $kubeconfig apply -f -
    Assert-NativeSuccess 'Install public RDS CA bundle'
    $foundation=Get-Content .local/deployment/foundation-outputs.json -Raw|ConvertFrom-Json
    $bi=Get-Content .local/deployment/bi-outputs.json -Raw|ConvertFrom-Json
    @{image=$images.bootstrap; databaseHost=$foundation.database_host.value; masterSecretArn=$foundation.database_master_secret_arn.value;
      appSecretArn=$bi.secret_arns.value.'metabase-app'; reportingSecretArn=$bi.secret_arns.value.'metabase-reporting'}|
      ConvertTo-Json|Set-Content .local/deployment/bi-bootstrap-values.json -Encoding utf8
    & $helm upgrade --install wonderland-bi-bootstrap deploy/helm/bi-bootstrap --namespace wonderland-bootstrap --kubeconfig $kubeconfig -f .local/deployment/bi-bootstrap-values.json --timeout 120s
    Assert-NativeSuccess 'Install reviewed private bootstrap Job'
    & $kubectl --kubeconfig $kubeconfig -n wonderland-bootstrap wait --for=condition=complete job/wonderland-bi-bootstrap --timeout=900s
    $waitResult=$LASTEXITCODE
    $logs=& $kubectl --kubeconfig $kubeconfig -n wonderland-bootstrap logs job/wonderland-bi-bootstrap
    Assert-NativeSuccess 'Read sanitized BI bootstrap report'
    $logs|Set-Content .local/deployment/step10e-bootstrap.log -Encoding utf8
    if ($waitResult -ne 0) {throw 'Bootstrap incomplete; inspect sanitized log before retry'}
    $lines=@($logs|Where-Object{$_ -like 'BI_BOOTSTRAP_REPORT=*'})
    if ($lines.Count -ne 1) {throw 'Expected one bootstrap report'}
    $report=$lines[0].Substring('BI_BOOTSTRAP_REPORT='.Length)|ConvertFrom-Json
    if ($report.status -ne 'VERIFIED' -or @($report.checks.PSObject.Properties|Where-Object{$_.Value -ne $true}).Count) {throw 'BI verification failed'}
    $report|Add-Member -NotePropertyName verified_at_utc -NotePropertyValue ([DateTime]::UtcNow.ToString('o'))
    $report|ConvertTo-Json -Depth 12|Set-Content docs/evidence/step10e-database-verification.json -Encoding utf8
    return
}
if ($Deploy) {
    $report=Get-Content docs/evidence/step10e-database-verification.json -Raw|ConvertFrom-Json
    if ($report.status -ne 'VERIFIED') {throw 'Verified database initialization required'}
    $images=Get-Content .local/deployment/bi-images.json -Raw|ConvertFrom-Json
    $values=Get-Content .local/deployment/workload-values.json -Raw|ConvertFrom-Json
    if ($values.pricingMode -ne 'projection' -or $values.frontendOrigin -ne 'https://main.d3vt08cs3xnlse.amplifyapp.com') {throw 'Unexpected existing app configuration'}
    $values.images.analytics=$images.analytics
    $values|ConvertTo-Json -Depth 14|Set-Content .local/deployment/workload-values.json -Encoding utf8
    & $helm upgrade wonderland deploy/helm/wonderland --namespace wonderland --kubeconfig $kubeconfig -f .local/deployment/workload-values.json --wait --timeout 600s
    Assert-NativeSuccess 'Roll out only the two new analytics workers'
    & $helm upgrade --install wonderland-metabase deploy/helm/metabase --namespace wonderland --kubeconfig $kubeconfig --wait --timeout 1200s
    Assert-NativeSuccess 'Start private durable Metabase'
}
