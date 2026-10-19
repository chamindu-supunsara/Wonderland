param([switch]$RemoveCompletedJob)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'aws-common.ps1')
Set-Location $ProjectRoot
$env:AWS_PROFILE = 'wonderland-feasibility'
$env:PATH = (Split-Path $LocalAws -Parent) + [IO.Path]::PathSeparator + $env:PATH
$kubectl = Join-Path $ProjectRoot '.local/tools/kubectl.exe'
$helm = Join-Path $ProjectRoot '.local/tools/helm/windows-amd64/helm.exe'
$kubeconfig = Join-Path $ProjectRoot '.local/deployment/kubeconfig'
$release = 'wonderland-db-bootstrap'
$namespace = 'wonderland-bootstrap'
if ($RemoveCompletedJob) {
    # Export and verify the report before removing the privileged Kubernetes identity.
    $report = Get-Content 'docs/evidence/step10b-database-verification.json' -Raw | ConvertFrom-Json
    if ($report.status -ne 'VERIFIED') { throw 'A verified database report is required before cleanup.' }
    & $helm uninstall $release --namespace $namespace --kubeconfig $kubeconfig --wait --timeout 120s
    Assert-NativeSuccess 'Remove bootstrap Job, service account and restricted RBAC'
    return
}
$identity = (& $LocalAws sts get-caller-identity --output json --no-cli-pager) | ConvertFrom-Json
Assert-NativeSuccess 'Verify operator identity'
if ($identity.Account -ne '708919751353' -or $identity.Arn -notmatch ':assumed-role/AWSReservedSSO_WonderlandFeasibility_') { throw 'Unexpected AWS operator identity.' }
$current = (& $LocalAws sso-admin get-inline-policy-for-permission-set --instance-arn arn:aws:sso:::instance/ssoins-65954bc9fbd03036 --permission-set-arn arn:aws:sso:::permissionSet/ssoins-65954bc9fbd03036/ps-659523c3e5c38026 --output json --no-cli-pager) | ConvertFrom-Json
Assert-NativeSuccess 'Read provisioned operator policy'
# Compare parsed policy trees using Python, so JSON property order is irrelevant.
$current.InlinePolicy | Set-Content '.local/deployment/database-current-policy.json' -Encoding utf8
& ./.venv/Scripts/python.exe -c 'import json; from pathlib import Path; p=Path(".local/deployment"); assert json.loads((p/"database-current-policy.json").read_text(encoding="utf-8-sig")) == json.loads((p/"database-merged-policy.json").read_text(encoding="utf-8-sig")), "Unreviewed operator policy"'
Assert-NativeSuccess 'Compare reviewed operator policy'
$stack = (& $LocalAws cloudformation describe-stacks --stack-name wonderland-db-bootstrap-access --query 'Stacks[0].StackStatus' --output text --no-cli-pager).Trim()
Assert-NativeSuccess 'Verify temporary bootstrap identity stack'
if ($stack -notin @('CREATE_COMPLETE', 'UPDATE_COMPLETE')) { throw "Bootstrap access stack is not ready: $stack" }
$outputs = Get-Content '.local/deployment/foundation-outputs.json' -Raw | ConvertFrom-Json
$repository = $outputs.repositories.value.catalog
if ($repository -ne '708919751353.dkr.ecr.ap-south-1.amazonaws.com/wonderland-demo/catalog') { throw 'Unexpected bootstrap image repository.' }
& docker build --file deploy/database_bootstrap/Dockerfile --tag wonderland-db-bootstrap:step10b .
Assert-NativeSuccess 'Build reviewed bootstrap image'
$imageId = (& docker image inspect wonderland-db-bootstrap:step10b --format '{{.Id}}').Trim()
Assert-NativeSuccess 'Inspect bootstrap image'
$tag = 'db-bootstrap-' + $imageId.Substring(7, 16)
$target = $repository + ':' + $tag
$registry = '708919751353.dkr.ecr.ap-south-1.amazonaws.com'
$dockerConfig = Join-Path $ProjectRoot '.local/deployment/docker-auth'
New-Item -ItemType Directory -Path $dockerConfig -Force | Out-Null
try {
    $token = & $LocalAws ecr get-login-password --region ap-south-1
    Assert-NativeSuccess 'Obtain temporary ECR authentication'
    $token | & docker --config $dockerConfig login --username AWS --password-stdin $registry
    Assert-NativeSuccess 'Authenticate Docker to reviewed ECR registry'
    $token = $null
    & docker tag wonderland-db-bootstrap:step10b $target
    Assert-NativeSuccess 'Tag bootstrap image'
    # Immutable tags: a previously successful push can be reused on retry.
    $digest = & $LocalAws ecr describe-images --repository-name wonderland-demo/catalog --image-ids "imageTag=$tag" --query 'imageDetails[0].imageDigest' --output text --no-cli-pager 2>$null
    if ($LASTEXITCODE -ne 0) {
        & docker --config $dockerConfig push $target
        Assert-NativeSuccess 'Push bootstrap image to ECR'
        $digest = & $LocalAws ecr describe-images --repository-name wonderland-demo/catalog --image-ids "imageTag=$tag" --query 'imageDetails[0].imageDigest' --output text --no-cli-pager
        Assert-NativeSuccess 'Resolve uploaded image digest'
    }
} finally {
    $token = $null
    # This directory contains only this script's disposable Docker login configuration.
    $authFile = Join-Path $dockerConfig 'config.json'
    if (Test-Path -LiteralPath $authFile) { Remove-Item -LiteralPath $authFile -Force }
}
$digest = "$digest".Trim()
if ($digest -notmatch '^sha256:[a-f0-9]{64}$') { throw 'ECR did not return a valid image digest.' }
$values = @{ image = "$repository@$digest"; databaseHost = $outputs.database_host.value; masterSecretArn = $outputs.database_master_secret_arn.value; serviceSecretArns = $outputs.service_secret_arns.value }
$values | ConvertTo-Json -Depth 10 | Set-Content '.local/deployment/database-bootstrap-values.json' -Encoding utf8
& $LocalAws eks update-kubeconfig --name wonderland-demo --profile wonderland-feasibility --region ap-south-1 --kubeconfig $kubeconfig --alias wonderland-demo --no-cli-pager
Assert-NativeSuccess 'Refresh isolated kubeconfig'
& $kubectl --kubeconfig $kubeconfig apply -f deploy/database_bootstrap/runtime-prerequisites.yaml
Assert-NativeSuccess 'Create runtime Secret placeholders and restricted namespaces'
& $helm lint deploy/helm/database-bootstrap --strict --namespace $namespace -f .local/deployment/database-bootstrap-values.json
Assert-NativeSuccess 'Lint bootstrap release'
# A failed or completed prior Job must be reviewed and explicitly removed before retry.
& $helm upgrade --install $release deploy/helm/database-bootstrap --namespace $namespace --kubeconfig $kubeconfig -f .local/deployment/database-bootstrap-values.json --timeout 120s
Assert-NativeSuccess 'Install temporary bootstrap release'
& $kubectl --kubeconfig $kubeconfig -n $namespace wait --for=condition=complete "job/$release" --timeout=900s
$waitCode = $LASTEXITCODE
$logs = & $kubectl --kubeconfig $kubeconfig -n $namespace logs "job/$release"
Assert-NativeSuccess 'Read sanitized bootstrap report'
$logs | Set-Content '.local/deployment/database-bootstrap.log' -Encoding utf8
if ($waitCode -ne 0) { throw 'Bootstrap did not complete. Review the sanitized Job log before retry; do not print credentials.' }
$line = @($logs | Where-Object { $_ -like 'BOOTSTRAP_REPORT=*' })
if ($line.Count -ne 1) { throw 'Expected exactly one bootstrap verification report.' }
$result = $line[0].Substring('BOOTSTRAP_REPORT='.Length) | ConvertFrom-Json
if ($result.status -ne 'VERIFIED' -or $result.checkout -ne 'mock') { throw 'Database verification did not pass.' }
$result | Add-Member -NotePropertyName image -NotePropertyValue "$repository@$digest"
$result | Add-Member -NotePropertyName verified_at_utc -NotePropertyValue ([DateTime]::UtcNow.ToString('o'))
$result | Add-Member -NotePropertyName temporary_access_removed -NotePropertyValue $false
$result | ConvertTo-Json -Depth 12 | Set-Content 'docs/evidence/step10b-database-verification.json' -Encoding utf8
Write-Host 'Database verified. Next export evidence, uninstall this bootstrap release and remove its temporary owner access stack.'
