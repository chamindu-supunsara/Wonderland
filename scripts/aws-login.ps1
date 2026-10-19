param([string]$Profile = 'wonderland-worker-source')
. "$PSScriptRoot\aws-common.ps1"
& $LocalAws login --profile $Profile --region ap-south-1
Assert-NativeSuccess 'Temporary AWS login'

