. "$PSScriptRoot\common.ps1"
$LocalAws = Join-Path $ProjectRoot '.local\tools\aws-cli\Amazon\AWSCLIV2\aws.exe'
if (-not (Test-Path -LiteralPath $LocalAws)) {
    $LocalAws = (Get-Command aws -ErrorAction Stop).Source
}
# EKS kubeconfig invokes `aws` by name. Make the bundled CLI available in this process.
$awsToolDirectory = Split-Path $LocalAws -Parent
if (($env:PATH -split [IO.Path]::PathSeparator) -notcontains $awsToolDirectory) {
    $env:PATH = $awsToolDirectory + [IO.Path]::PathSeparator + $env:PATH
}
$env:AWS_CONFIG_FILE = Join-Path $ProjectRoot '.local\aws\config'
$env:AWS_LOGIN_CACHE_DIRECTORY = Join-Path $ProjectRoot '.local\aws\login\cache'
$env:AWS_DEFAULT_REGION = 'ap-south-1'
$env:AWS_EC2_METADATA_DISABLED = 'true'
$env:PYTHONPATH = Join-Path $ProjectRoot 'packages\common'

