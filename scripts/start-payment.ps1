. "$PSScriptRoot\common.ps1"
Assert-ProjectPython
Push-Location (Join-Path $ProjectRoot 'services\payment')
try {
    & $ProjectPython -m uvicorn payment_app.main:app --host 127.0.0.1 --port 8003 --reload
    Assert-NativeSuccess 'Running MOCK Payment API'
} finally { Pop-Location }
