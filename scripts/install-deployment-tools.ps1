$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path $PSScriptRoot -Parent
$toolDirectory = Join-Path $repoRoot '.local/tools'
New-Item -ItemType Directory -Force -Path $toolDirectory | Out-Null
$packages = @(
    @{
        File = 'terraform_1.16.6_windows_amd64.zip'
        Url = 'https://releases.hashicorp.com/terraform/1.16.6/terraform_1.16.6_windows_amd64.zip'
        Hash = '6ea2c186e0e76a113af30fbcdcf7a4b4c70756317994a04929e5c90b9e94b1df'
        Directory = 'terraform'
    },
    @{
        File = 'helm-v4.3.1-windows-amd64.zip'
        Url = 'https://get.helm.sh/helm-v4.3.1-windows-amd64.zip'
        Hash = 'fcfd7b796dcf0f225abc40b5636a3b01f55f3de2fb1dfb18475df94e62c14112'
        Directory = 'helm'
    }
)
foreach ($package in $packages) {
    $archive = Join-Path $toolDirectory $package.File
    if (-not (Test-Path -LiteralPath $archive)) { Invoke-WebRequest $package.Url -OutFile $archive }
    if ((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash -ine $package.Hash) {
        throw "Checksum mismatch: $archive. Do not run this archive; investigate before replacing it."
    }
    Expand-Archive -LiteralPath $archive -DestinationPath (Join-Path $toolDirectory $package.Directory) -Force
}
& (Join-Path $toolDirectory 'terraform/terraform.exe') version
if ($LASTEXITCODE -ne 0) { throw 'Terraform failed to run.' }
& (Join-Path $toolDirectory 'helm/windows-amd64/helm.exe') version --short
if ($LASTEXITCODE -ne 0) { throw 'Helm failed to run.' }
