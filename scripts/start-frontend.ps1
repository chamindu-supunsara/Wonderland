. "$PSScriptRoot\common.ps1"
Push-Location (Join-Path $ProjectRoot 'frontend')
try {
    if (-not (Test-Path -LiteralPath 'node_modules')) { throw 'Run scripts\setup.ps1 first.' }
    & npm.cmd start
    Assert-NativeSuccess 'Running Angular'
} finally { Pop-Location }

