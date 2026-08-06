param(
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$FrontendDir = Join-Path $ProjectRoot "frontend"
$ElectronDir = Join-Path $ProjectRoot "electron"

function Assert-Command([string]$Name) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "$Name was not found. Install Node.js 18+ and reopen PowerShell."
    }
}

Assert-Command "npm"

if (-not $SkipInstall) {
    if (-not (Test-Path (Join-Path $FrontendDir "node_modules"))) {
        Push-Location $FrontendDir
        try { npm ci } finally { Pop-Location }
    }
    if (-not (Test-Path (Join-Path $ElectronDir "node_modules"))) {
        Push-Location $ElectronDir
        try { npm ci } finally { Pop-Location }
    }
}

$electronBinary = Join-Path $ElectronDir "node_modules\electron\dist\electron.exe"
$electronPathFile = Join-Path $ElectronDir "node_modules\electron\path.txt"
if (-not (Test-Path $electronBinary)) {
    Write-Host "Electron binary is missing. Running its install script again..." -ForegroundColor Yellow
    Push-Location $ElectronDir
    try { npm rebuild electron --foreground-scripts } finally { Pop-Location }
}
if (-not (Test-Path $electronBinary)) {
    throw "Electron is still incomplete. Check npm network access, delete electron/node_modules/electron, and rerun this script."
}

# Electron's launcher reads path.txt verbatim, so it must not contain a trailing newline.
$expectedElectronPath = "electron.exe"
$installedElectronPath = if (Test-Path $electronPathFile) {
    [IO.File]::ReadAllText($electronPathFile)
} else {
    ""
}
if ($installedElectronPath -ne $expectedElectronPath) {
    [IO.File]::WriteAllText($electronPathFile, $expectedElectronPath, [Text.UTF8Encoding]::new($false))
}

$frontendProcess = $null
$frontendStarted = $false
try {
    $ready = $false
    try {
        $response = Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:5173" -TimeoutSec 2
        $ready = $response.StatusCode -eq 200
    } catch {}

    if (-not $ready) {
        $frontendProcess = Start-Process -FilePath "npm.cmd" -ArgumentList @('run', 'dev', '--', '--host', '127.0.0.1') -WorkingDirectory $FrontendDir -WindowStyle Hidden -PassThru
        $frontendStarted = $true
    }

    $deadline = (Get-Date).AddSeconds(30)
    while (-not $ready -and (Get-Date) -lt $deadline) {
        try {
            $response = Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:5173" -TimeoutSec 2
            if ($response.StatusCode -eq 200) { $ready = $true; break }
        } catch {}
        Start-Sleep -Milliseconds 500
    }
    if (-not $ready) { throw "Vite did not become ready within 30 seconds." }

    Write-Host "VerseNa Electron development mode is starting. Use the tray menu Exit command to stop it." -ForegroundColor Green
    Push-Location $ElectronDir
    try { npm start } finally { Pop-Location }
} finally {
    if ($frontendStarted -and $frontendProcess -and -not $frontendProcess.HasExited) {
        & taskkill.exe /PID $frontendProcess.Id /T /F 2>$null | Out-Null
    }
}
