param([switch]$NoReload)
. "$PSScriptRoot\common.ps1"
Assert-ProjectPython
Push-Location (Join-Path $ProjectRoot 'services\catalog')
try {
    if (-not (Test-Path -LiteralPath '.env')) { throw 'Missing catalog .env. Run scripts\setup.ps1.' }
    $ServerArguments = @('-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8001')
    if (-not $NoReload) { $ServerArguments += '--reload' }
    & $ProjectPython @ServerArguments
    Assert-NativeSuccess 'Running the catalog API'
} finally { Pop-Location }

