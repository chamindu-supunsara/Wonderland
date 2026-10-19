$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path $PSScriptRoot -Parent
Set-Location $repoRoot
$terraformTool = Join-Path $repoRoot '.local/tools/terraform/terraform.exe'
$helmTool = Join-Path $repoRoot '.local/tools/helm/windows-amd64/helm.exe'
$pythonTool = Join-Path $repoRoot '.venv/Scripts/python.exe'
foreach ($tool in @($terraformTool, $helmTool, $pythonTool)) {
    if (-not (Test-Path -LiteralPath $tool)) { throw "Missing deployment tool: $tool. Follow docs/steps/10-cloud-deployment.md." }
}
function Invoke-Checked([string]$Tool, [string[]]$Arguments) {
    & $Tool @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Validation failed: $Tool $Arguments" }
}
Invoke-Checked $terraformTool @('fmt', '-recursive', '-check', 'infra/terraform')
$previousDataDirectory = $env:TF_DATA_DIR
$previousPluginCache = $env:TF_PLUGIN_CACHE_DIR
try {
    # Never reuse the live roots' initialized S3 backend metadata for local tests.
    $installedProviders = Join-Path $repoRoot 'infra/terraform/foundation/.terraform/providers'
    if (Test-Path -LiteralPath $installedProviders) { $env:TF_PLUGIN_CACHE_DIR = $installedProviders }
    foreach ($root in @('bootstrap', 'foundation')) {
        $env:TF_DATA_DIR = Join-Path $repoRoot ".local/deployment/validation/$root"
        $changeDirectory = "-chdir=infra/terraform/$root"
        Invoke-Checked $terraformTool @($changeDirectory, 'init', '-backend=false', '-input=false', '-no-color')
        Invoke-Checked $terraformTool @($changeDirectory, 'validate', '-no-color')
        # All test files explicitly mock every provider; no real cloud plan/apply runs here.
        Invoke-Checked $terraformTool @($changeDirectory, 'test', '-no-color')
    }
} finally {
    $env:TF_DATA_DIR = $previousDataDirectory
    $env:TF_PLUGIN_CACHE_DIR = $previousPluginCache
}
Invoke-Checked $helmTool @('lint', 'deploy/helm/wonderland', '--kube-version', '1.35.0', '--strict')
Invoke-Checked $helmTool @('lint', 'deploy/helm/wonderland', '-f', 'deploy/helm/tests/render-values.yaml', '--kube-version', '1.35.0', '--strict')
Invoke-Checked $pythonTool @('-m', 'pytest', 'tests/test_deployment_chart.py', 'tests/test_bootstrap_policy_merge.py', 'tests/test_foundation_policy_merge.py', '-q')
Write-Host 'Local deployment validation passed. No AWS resources were created.'
