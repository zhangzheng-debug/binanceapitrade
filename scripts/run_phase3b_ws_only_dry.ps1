$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir "..")
Set-Location $ProjectRoot

$python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    throw "Missing .venv\Scripts\python.exe. Create the project venv before running Phase 3B."
}

$env:DRY_RUN = "true"
$env:LIVE_TRADING = "false"
$env:PUBLIC_MARKET_DRY_RUN = "true"
$env:PUBLIC_MARKET_WS_ONLY = "true"
$env:ALLOW_CACHED_EXCHANGE_FILTERS_IN_DRY_RUN = "true"
$env:CACHED_EXCHANGE_FILTERS_PATH = if ($env:CACHED_EXCHANGE_FILTERS_PATH) { $env:CACHED_EXCHANGE_FILTERS_PATH } else { ".\config\exchange_filters_ETHUSDC.json" }
$env:REQUIRE_REST_EXCHANGE_INFO_FOR_LIVE = "true"
$env:REQUIRE_SIGNED_REST_VALIDATION_FOR_TESTNET = "true"
$env:TESTNET_ORDER_TEST = "false"
$env:BINANCE_SYMBOL = "ETHUSDC"
$env:BINANCE_INTERVAL = "15m"
$env:BINANCE_ENV = if ($env:BINANCE_ENV) { $env:BINANCE_ENV } else { "mainnet" }
$env:EXIT_AFTER_BOUNDED_RUNTIME = "true"
$env:PHASE3B_BOUNDED_RUNTIME_SECONDS = if ($env:PHASE3B_BOUNDED_RUNTIME_SECONDS) { $env:PHASE3B_BOUNDED_RUNTIME_SECONDS } else { "3600" }
$env:PUBLIC_MARKET_DRY_RUN_SECONDS = $env:PHASE3B_BOUNDED_RUNTIME_SECONDS
$env:BINANCE_API_KEY = ""
$env:BINANCE_API_SECRET = ""
$env:LOG_LEVEL = if ($env:LOG_LEVEL) { $env:LOG_LEVEL } else { "DEBUG" }

& $python -m bot.main
