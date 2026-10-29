param(
    [int]$Port = 8001
)

$ErrorActionPreference = 'Stop'
$taskBackendDirectory = Join-Path $PSScriptRoot '..\backend'
$taskPython = Join-Path $taskBackendDirectory '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) {
    throw 'Backend Python environment missing: create backend/.venv and install backend/requirements.txt first.'
}

# Resolve .env, SQLite and private storage paths from the backend directory.
Push-Location -LiteralPath $taskBackendDirectory
try {
    & $taskPython -m uvicorn app.main:app --host 127.0.0.1 --port $Port
    if ($LASTEXITCODE -ne 0) {
        throw "Backend exited with code $LASTEXITCODE."
    }
} finally {
    Pop-Location
}
