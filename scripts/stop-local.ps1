. "$PSScriptRoot\common.ps1"
Push-Location $ProjectRoot
try {
    # Preserve the named database volume. Stop host dev servers with Ctrl+C.
    & docker compose stop
    Assert-NativeSuccess 'Stopping local containers'
} finally { Pop-Location }

