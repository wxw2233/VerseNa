param(
    [ValidateSet("installer", "dir")]
    [string]$Target = "installer",
    [string]$PipIndexUrl = "https://mirrors.aliyun.com/pypi/simple/"
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$BuildRoot = Join-Path $ProjectRoot "build\windows"
$RuntimeDir = Join-Path $BuildRoot "python"
$CacheDir = Join-Path $ProjectRoot "build\cache"
$PythonVersion = "3.11.9"
$PythonArchive = Join-Path $CacheDir "python-$PythonVersion-embed-amd64.zip"
$PythonUrl = "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-embed-amd64.zip"
$HostPython = (Get-Command python -ErrorAction Stop).Source
$MinPythonArchiveBytes = 5MB

function Remove-BuildDirectory([string]$Path) {
    $resolvedRoot = (Resolve-Path $ProjectRoot).Path
    $resolvedPath = [IO.Path]::GetFullPath($Path)
    $allowedPrefix = [IO.Path]::Combine($resolvedRoot, "build") + [IO.Path]::DirectorySeparatorChar
    if (-not $resolvedPath.StartsWith($allowedPrefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove a path outside the project build directory: $resolvedPath"
    }
    if (Test-Path $resolvedPath) { Remove-Item -LiteralPath $resolvedPath -Recurse -Force }
}

New-Item -ItemType Directory -Force -Path $CacheDir | Out-Null
Remove-BuildDirectory $BuildRoot
New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null

function Download-PythonArchive {
    $TempArchive = "$PythonArchive.download"
    Remove-Item -LiteralPath $TempArchive -Force -ErrorAction SilentlyContinue
    Write-Host "Downloading Python $PythonVersion embeddable runtime..." -ForegroundColor Cyan
    $Curl = Get-Command curl.exe -ErrorAction SilentlyContinue
    if ($Curl) {
        & $Curl.Source -L --fail --retry 3 --connect-timeout 30 --output $TempArchive $PythonUrl
        if ($LASTEXITCODE -ne 0) { throw "Python archive download failed" }
    } else {
        Invoke-WebRequest -Uri $PythonUrl -OutFile $TempArchive
    }
    $ArchiveInfo = Get-Item -LiteralPath $TempArchive
    if ($ArchiveInfo.Length -lt $MinPythonArchiveBytes) {
        Remove-Item -LiteralPath $TempArchive -Force -ErrorAction SilentlyContinue
        throw "Downloaded Python archive is unexpectedly small ($($ArchiveInfo.Length) bytes)"
    }
    Move-Item -LiteralPath $TempArchive -Destination $PythonArchive -Force
}

if ((-not (Test-Path $PythonArchive)) -or ((Get-Item -LiteralPath $PythonArchive).Length -lt $MinPythonArchiveBytes)) {
    Remove-Item -LiteralPath $PythonArchive -Force -ErrorAction SilentlyContinue
    Download-PythonArchive
}

try {
    Expand-Archive -LiteralPath $PythonArchive -DestinationPath $RuntimeDir -Force
} catch {
    Write-Host "Python archive looks broken, redownloading..." -ForegroundColor Yellow
    Remove-BuildDirectory $RuntimeDir
    New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null
    Remove-Item -LiteralPath $PythonArchive -Force -ErrorAction SilentlyContinue
    Download-PythonArchive
    Expand-Archive -LiteralPath $PythonArchive -DestinationPath $RuntimeDir -Force
}
$PthFile = Get-ChildItem $RuntimeDir -Filter "python*._pth" | Select-Object -First 1
if (-not $PthFile) { throw "Embedded Python _pth file was not found" }
$PthLines = @(Get-Content -Encoding UTF8 $PthFile.FullName)
if ($PthLines -notcontains "Lib/site-packages") { $PthLines += "Lib/site-packages" }
if ($PthLines -notcontains "..\backend") { $PthLines += "..\backend" }
$PthLines = $PthLines | ForEach-Object {
    if ($_ -eq "#import site") { "import site" } else { $_ }
}
[IO.File]::WriteAllLines($PthFile.FullName, $PthLines, [Text.UTF8Encoding]::new($false))

$SitePackages = Join-Path $RuntimeDir "Lib\site-packages"
New-Item -ItemType Directory -Force -Path $SitePackages | Out-Null
Write-Host "Installing backend runtime dependencies..." -ForegroundColor Cyan
& $HostPython -m pip install `
    --isolated `
    --disable-pip-version-check `
    --no-compile `
    --upgrade `
    --index-url $PipIndexUrl `
    --trusted-host ([Uri]$PipIndexUrl).Host `
    --target $SitePackages `
    -r (Join-Path $ProjectRoot "backend\requirements-runtime.txt")
if ($LASTEXITCODE -ne 0) { throw "Python dependency installation failed" }

$RuntimePython = Join-Path $RuntimeDir "python.exe"
& $RuntimePython -c "import fastapi, uvicorn, aiosqlite, httpx, pydantic; print('Embedded backend runtime OK')"
if ($LASTEXITCODE -ne 0) { throw "Embedded Python runtime verification failed" }

Push-Location (Join-Path $ProjectRoot "frontend")
try {
    if (-not (Test-Path "node_modules")) { npm ci }
    npm run build
    if ($LASTEXITCODE -ne 0) { throw "Frontend build failed" }
} finally { Pop-Location }

Push-Location (Join-Path $ProjectRoot "electron")
try {
    if (-not (Test-Path "node_modules")) { npm ci }
    $buildScript = if ($Target -eq "dir") { "build:dir" } else { "build" }
    npm run $buildScript
    if ($LASTEXITCODE -ne 0) { throw "Electron packaging failed" }
} finally { Pop-Location }

Write-Host ""
Write-Host "Windows package ready under $ProjectRoot\dist-electron" -ForegroundColor Green
