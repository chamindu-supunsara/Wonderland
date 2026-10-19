param(
    [Parameter(Mandatory)][ValidatePattern('^[a-z]{2}(-[a-z]+)+-[0-9]$')][string]$Region,
    [Parameter(Mandatory)][ValidatePattern('^[a-z]{2}(-[a-z]+)+-[0-9]_[A-Za-z0-9]+$')][string]$UserPoolId,
    [Parameter(Mandatory)][ValidatePattern('^[a-zA-Z0-9]{1,128}$')][string]$ClientId
)
. "$PSScriptRoot\common.ps1"
Assert-ProjectPython
if (-not $UserPoolId.StartsWith("${Region}_")) { throw 'Pool ID and region must match.' }
& $ProjectPython (Join-Path $PSScriptRoot 'connect_cognito.py') --region $Region --pool-id $UserPoolId --client-id $ClientId
Assert-NativeSuccess 'Connecting Cognito configuration'

