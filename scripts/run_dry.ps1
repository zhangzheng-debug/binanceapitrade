$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

if (-not (Test-Path -LiteralPath ".env")) {
  Write-Host ".env not found; using process-level dry-run defaults. Copy .env.example to .env when ready."
}

$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python)) {
  $Python = "python"
}

$env:DRY_RUN = "true"
$env:LIVE_TRADING = "false"
$env:PUBLIC_MARKET_DRY_RUN = "false"
& $Python -m bot.main
