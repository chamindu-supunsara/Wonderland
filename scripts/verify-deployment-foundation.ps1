$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'aws-common.ps1')
Set-Location $ProjectRoot
$env:AWS_PROFILE = 'wonderland-feasibility'
$env:AWS_SDK_LOAD_CONFIG = '1'
# kubectl's generated exec-auth command uses `aws`; expose the bundled CLI in this process only.
$env:PATH = (Split-Path $LocalAws -Parent) + [IO.Path]::PathSeparator + $env:PATH
$identityText = & $LocalAws sts get-caller-identity --profile wonderland-feasibility --output json --no-cli-pager
Assert-NativeSuccess 'Read verification identity'
$identity = $identityText | ConvertFrom-Json
if ($identity.Account -ne '708919751353' -or $identity.Arn -notmatch ':assumed-role/AWSReservedSSO_WonderlandFeasibility_') {
    throw 'Use the verified non-root WonderlandFeasibility profile.'
}
$terraformTool = Join-Path $ProjectRoot '.local/tools/terraform/terraform.exe'
$kubectlTool = Join-Path $ProjectRoot '.local/tools/kubectl.exe'
$kubeconfig = Join-Path $ProjectRoot '.local/deployment/kubeconfig'
& $terraformTool '-chdir=infra/terraform/foundation' output -json | Set-Content '.local/deployment/foundation-outputs.json' -Encoding utf8
Assert-NativeSuccess 'Read foundation outputs'
& $LocalAws eks update-kubeconfig --name wonderland-demo --region ap-south-1 --profile wonderland-feasibility --kubeconfig $kubeconfig --alias wonderland-demo --no-cli-pager
Assert-NativeSuccess 'Write isolated workspace kubeconfig'
& $kubectlTool --kubeconfig $kubeconfig wait --for=condition=Ready nodes --all --timeout=180s
Assert-NativeSuccess 'Wait for worker nodes'
& $kubectlTool --kubeconfig $kubeconfig -n kube-system rollout status deployment/coredns --timeout=180s
Assert-NativeSuccess 'Wait for cluster DNS'
& $kubectlTool --kubeconfig $kubeconfig get nodes -o json | Set-Content '.local/deployment/foundation-nodes.json' -Encoding utf8
Assert-NativeSuccess 'Read node readiness'
& $kubectlTool --kubeconfig $kubeconfig get pods -n kube-system -o json | Set-Content '.local/deployment/foundation-system-pods.json' -Encoding utf8
Assert-NativeSuccess 'Read system pod readiness'
& .\.venv\Scripts\python.exe scripts/verify_foundation_deployment.py
Assert-NativeSuccess 'Verify foundation AWS and Kubernetes evidence'
Write-Host 'Foundation verified. No application images, migrations, checkout changes or Helm releases were deployed.'
