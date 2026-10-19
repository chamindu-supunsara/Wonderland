param([switch]$SkipFrontend)
. "$PSScriptRoot\common.ps1"
Push-Location $ProjectRoot
try {
    Assert-DockerEngine
    if (-not (Test-Path -LiteralPath $ProjectPython)) {
        & python -m venv .venv
        Assert-NativeSuccess 'Creating the Python environment'
    }
    & $ProjectPython -m pip install -r services/catalog/requirements-dev.txt
    Assert-NativeSuccess 'Installing Python dependencies'
    if (-not (Test-Path -LiteralPath 'services/catalog/.env')) {
        Copy-Item -LiteralPath 'services/catalog/.env.example' -Destination 'services/catalog/.env'
    }
    & docker compose up -d postgres --wait
    Assert-NativeSuccess 'Starting PostgreSQL'
    Push-Location 'services/catalog'
    try {
        & $ProjectPython -m alembic upgrade head
        Assert-NativeSuccess 'Applying catalog migrations'
        & $ProjectPython -m app.seed
        Assert-NativeSuccess 'Seeding demo data'
    } finally { Pop-Location }
    if (-not (Test-Path -LiteralPath 'services/booking/.env')) {
        $BookingConfig = (Get-Content -Raw services/catalog/.env).Replace('catalog_dev:catalog_dev_only', 'booking_dev:booking_dev_only')
        Set-Content -LiteralPath services/booking/.env -Value $BookingConfig
    }
    & docker compose up booking-bootstrap
    Assert-NativeSuccess 'Preparing Booking database roles and schemas'
    Push-Location 'services/booking'
    try {
        & $ProjectPython -m alembic upgrade head
        Assert-NativeSuccess 'Applying booking migrations'
        & $ProjectPython -m booking_app.seed
        Assert-NativeSuccess 'Seeding future visit slots'
    } finally { Pop-Location }
    & docker compose up events-bootstrap
    Assert-NativeSuccess 'Preparing Analytics database roles and schemas'
    if (-not (Test-Path -LiteralPath 'services/analytics/.env')) {
        Copy-Item -LiteralPath 'services/analytics/.env.example' -Destination 'services/analytics/.env'
    }
    Push-Location 'services/analytics'
    try {
        & $ProjectPython -m alembic upgrade head
        Assert-NativeSuccess 'Applying Analytics event inbox migration'
    } finally { Pop-Location }
    & docker compose up payment-bootstrap
    Assert-NativeSuccess 'Preparing separate Payment schemas'
    if (-not (Test-Path -LiteralPath 'services/payment/.env')) {
        $PaymentConfig = (Get-Content -Raw services/booking/.env).Replace('booking_dev:booking_dev_only', 'payment_dev:payment_dev_only').Replace('BOOKING_DATABASE_URL', 'PAYMENT_DATABASE_URL')
        Set-Content -LiteralPath services/payment/.env -Value $PaymentConfig
        Add-Content -LiteralPath services/payment/.env -Value 'BOOKING_URL=http://127.0.0.1:8002'
    }
    Push-Location 'services/payment'
    try {
        & $ProjectPython -m alembic upgrade head
        Assert-NativeSuccess 'Applying mock checkout migration'
    } finally { Pop-Location }
    & docker compose up admission-bootstrap
    Assert-NativeSuccess 'Preparing separate Admission schemas'
    if (-not (Test-Path -LiteralPath 'services/admission/.env')) {
        $AdmissionConfig = (Get-Content -Raw services/booking/.env).Replace('booking_dev:booking_dev_only', 'admission_dev:admission_dev_only').Replace('BOOKING_DATABASE_URL', 'ADMISSION_DATABASE_URL')
        Set-Content -LiteralPath services/admission/.env -Value $AdmissionConfig
        Add-Content -LiteralPath services/admission/.env -Value 'BOOKING_URL=http://127.0.0.1:8002'
    }
    Push-Location 'services/admission'
    try {
        & $ProjectPython -m alembic upgrade head
        Assert-NativeSuccess 'Applying mock Admission migration'
    } finally { Pop-Location }
    & docker compose up --build reporting-grants
    Assert-NativeSuccess 'Applying reporting migrations and restricted grants'
    if (-not $SkipFrontend) {
        Push-Location 'frontend'
        try {
            & npx.cmd --yes npm@11.6.2 ci
            Assert-NativeSuccess 'Installing locked Angular dependencies'
        } finally { Pop-Location }
    }
    Write-Host 'Setup complete. Run scripts\start-analytics.ps1 and scripts\start-frontend.ps1. See docs\steps\08-mock-analytics.md.'
} finally { Pop-Location }

