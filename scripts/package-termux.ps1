$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Version = (Get-Content -Raw -Encoding UTF8 (Join-Path $ProjectRoot "frontend\package.json") | ConvertFrom-Json).version
$BuildRoot = Join-Path $ProjectRoot "build\termux"
$StageRoot = Join-Path $BuildRoot "VerseNa"
$ReleaseDir = Join-Path $ProjectRoot "release"
$Archive = Join-Path $ReleaseDir "VerseNa-$Version-termux.tar.gz"

function Remove-BuildDirectory([string]$Path) {
    $resolvedRoot = (Resolve-Path $ProjectRoot).Path
    $resolvedPath = [IO.Path]::GetFullPath($Path)
    $allowedPrefix = [IO.Path]::Combine($resolvedRoot, "build") + [IO.Path]::DirectorySeparatorChar
    if (-not $resolvedPath.StartsWith($allowedPrefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove a path outside the project build directory: $resolvedPath"
    }
    if (Test-Path $resolvedPath) { Remove-Item -LiteralPath $resolvedPath -Recurse -Force }
}

Remove-BuildDirectory $BuildRoot
New-Item -ItemType Directory -Force -Path $StageRoot, $ReleaseDir | Out-Null

function Copy-Tree([string]$Source, [string]$Destination) {
    & robocopy $Source $Destination /E /R:1 /W:1 /XD data tests __pycache__ .pytest_cache /XF .env *.pyc *.pyo | Out-Host
    if ($LASTEXITCODE -ge 8) { throw "Failed to copy $Source" }
}

Copy-Tree (Join-Path $ProjectRoot "backend") (Join-Path $StageRoot "backend")
Copy-Tree (Join-Path $ProjectRoot "frontend\dist") (Join-Path $StageRoot "frontend\dist")
Copy-Tree (Join-Path $ProjectRoot "themes") (Join-Path $StageRoot "themes")
Copy-Tree (Join-Path $ProjectRoot "personas") (Join-Path $StageRoot "personas")
Copy-Tree (Join-Path $ProjectRoot "themepacks") (Join-Path $StageRoot "themepacks")
New-Item -ItemType Directory -Force -Path (Join-Path $StageRoot "scripts"), (Join-Path $StageRoot "docs") | Out-Null
Copy-Item (Join-Path $ProjectRoot "scripts\start-termux.sh") (Join-Path $StageRoot "scripts\start-termux.sh")
Copy-Item (Join-Path $ProjectRoot "README.md"), (Join-Path $ProjectRoot "docs\LAN_ACCESS.md") -Destination (Join-Path $StageRoot "docs") -Force

if (Test-Path $Archive) { Remove-Item -LiteralPath $Archive -Force }
tar -czf $Archive -C $BuildRoot VerseNa
if ($LASTEXITCODE -ne 0) { throw "Termux archive creation failed" }

Write-Host "Termux package ready: $Archive" -ForegroundColor Green
