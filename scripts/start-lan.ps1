$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$BackendDir = Join-Path $ProjectRoot "backend"
$EnvFile = Join-Path $BackendDir ".env"
$FrontendIndex = Join-Path $ProjectRoot "frontend\dist\index.html"
$DataDir = if ($env:VERSENA_DATA_DIR) { $env:VERSENA_DATA_DIR } else { Join-Path $BackendDir "data" }
$ToolWorkspace = if ($env:VERSENA_TOOL_WORKSPACE) { $env:VERSENA_TOOL_WORKSPACE } else { Join-Path $DataDir "workspace" }

if (-not (Test-Path $EnvFile)) {
    $Lines = @(
        "VERSENA_HOST=0.0.0.0"
        "VERSENA_PORT=8002"
        "VERSENA_AUTH_COOKIE_SECURE=false"
    )
    [System.IO.File]::WriteAllLines($EnvFile, $Lines, (New-Object System.Text.UTF8Encoding($false)))
}

$env:VERSENA_HOST = "0.0.0.0"
$env:VERSENA_PORT = "8002"

if (-not (Test-Path $FrontendIndex)) {
    Push-Location (Join-Path $ProjectRoot "frontend")
    try {
        npm run build
    } finally {
        Pop-Location
    }
}

$Addresses = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Where-Object { $_.IPAddress -notlike '127.*' -and $_.PrefixOrigin -ne 'WellKnown' } |
    Select-Object -ExpandProperty IPAddress -Unique

Write-Host ""
Write-Host "VerseNa LAN access" -ForegroundColor Cyan
foreach ($Address in $Addresses) {
    Write-Host "  http://${Address}:8002"
}
Write-Host "  Tool workspace: $ToolWorkspace"
Write-Host ""

Push-Location $BackendDir
try {
    python main.py
} finally {
    Pop-Location
}
