Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$ProjectPython = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
$env:PYTHONPATH = Join-Path $ProjectRoot 'packages\common'

function Assert-NativeSuccess([string]$Action) {
    if ($LASTEXITCODE -ne 0) { throw "$Action failed (exit $LASTEXITCODE). See the command output above." }
}

function Assert-ProjectPython {
    if (-not (Test-Path -LiteralPath $ProjectPython)) {
        throw 'Project Python is missing. Run scripts\setup.ps1 first.'
    }
}

function Assert-DockerEngine {
    & docker info --format '{{.ServerVersion}}' | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw 'Start Docker Desktop, wait for its Linux engine, then rerun this command.'
    }
}

