. "$PSScriptRoot\common.ps1"
Push-Location $ProjectRoot
try {
    Assert-DockerEngine
    & docker compose up -d --build catalog booking booking-maintenance payment admission analytics-mock metabase
    Assert-NativeSuccess 'Starting mock application, Analytics and Metabase'
    Write-Host 'Open http://127.0.0.1:3000 and sign in to your separate local Metabase account.'
} finally { Pop-Location }
