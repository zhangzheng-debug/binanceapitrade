$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python)) {
  $Python = "python"
}

$env:DRY_RUN = "true"
$env:LIVE_TRADING = "false"
$env:PUBLIC_MARKET_DRY_RUN = "true"
$env:PUBLIC_MARKET_DRY_RUN_SECONDS = if ($env:PUBLIC_MARKET_DRY_RUN_SECONDS) { $env:PUBLIC_MARKET_DRY_RUN_SECONDS } else { "20" }
$env:BINANCE_ENV = "mainnet"
$env:BINANCE_SYMBOL = "ETHUSDC"
$env:BINANCE_INTERVAL = "15m"
$env:LOG_LEVEL = if ($env:LOG_LEVEL) { $env:LOG_LEVEL } else { "DEBUG" }

& $Python -m bot.main
