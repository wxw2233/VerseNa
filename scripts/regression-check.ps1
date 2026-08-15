$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$BackendDir = Join-Path $ProjectRoot "backend"
$FrontendDir = Join-Path $ProjectRoot "frontend"

Write-Host "[1/4] Backend tests" -ForegroundColor Cyan
Push-Location $ProjectRoot
try {
    python -m pytest backend/tests -q
} finally {
    Pop-Location
}

Write-Host "[2/4] Python compile check" -ForegroundColor Cyan
$PythonFiles = Get-ChildItem $BackendDir -Recurse -Filter *.py -File |
    Where-Object { $_.FullName -notmatch "\\(__pycache__|data)\\" } |
    Select-Object -ExpandProperty FullName
python -m py_compile $PythonFiles

Write-Host "[3/4] Frontend production build" -ForegroundColor Cyan
Push-Location $FrontendDir
try {
    npm run build
} finally {
    Pop-Location
}

Write-Host "[4/4] Git whitespace check" -ForegroundColor Cyan
git -C $ProjectRoot diff --check
Write-Host "VerseNa regression checks passed." -ForegroundColor Green
