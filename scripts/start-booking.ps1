. "$PSScriptRoot\common.ps1"
Assert-ProjectPython
Push-Location (Join-Path $ProjectRoot 'services\booking')
try {
    & $ProjectPython -m uvicorn booking_app.main:app --host 127.0.0.1 --port 8002 --reload
    Assert-NativeSuccess 'Running Booking API'
} finally { Pop-Location }
