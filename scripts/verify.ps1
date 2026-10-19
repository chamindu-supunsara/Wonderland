param([switch]$SkipFrontend)
. "$PSScriptRoot\common.ps1"
Assert-ProjectPython
Push-Location $ProjectRoot
try {
    Assert-DockerEngine
    & docker compose up booking-bootstrap
    Assert-NativeSuccess 'Preparing separate Booking schemas'
    & docker compose up events-bootstrap
    Assert-NativeSuccess 'Preparing separate Analytics schemas'
    & docker compose up payment-bootstrap
    Assert-NativeSuccess 'Preparing separate Payment schemas'
    & docker compose up admission-bootstrap
    Assert-NativeSuccess 'Preparing separate Admission schemas'
    & docker compose up reporting-bootstrap
    Assert-NativeSuccess 'Preparing local reporting roles'
    & $ProjectPython -m ruff check services/catalog services/booking services/payment services/admission services/analytics packages/common/wonderland_events tests
    Assert-NativeSuccess 'Python lint'
    & $ProjectPython -m ruff format --check services/catalog services/booking services/payment services/admission services/analytics packages/common/wonderland_events tests
    Assert-NativeSuccess 'Python formatting'
    & $ProjectPython -m pytest --tb=short
    Assert-NativeSuccess 'PostgreSQL integration tests'
    if (-not $SkipFrontend) {
        Push-Location frontend
        try {
            & npm.cmd test
            Assert-NativeSuccess 'Angular tests'
            & npm.cmd run build
            Assert-NativeSuccess 'Angular production build'
        } finally { Pop-Location }
    }
    Write-Host 'All milestone checks passed.'
} finally { Pop-Location }

