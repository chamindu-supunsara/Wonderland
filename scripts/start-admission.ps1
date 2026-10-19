. "$PSScriptRoot\common.ps1"
Assert-ProjectPython
Push-Location (Join-Path $ProjectRoot 'services\admission')
try {
    & $ProjectPython -m uvicorn admission_app.main:app --host 127.0.0.1 --port 8004 --reload
    Assert-NativeSuccess 'Running MOCK Admission API'
} finally { Pop-Location }
