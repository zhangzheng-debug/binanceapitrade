$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

python check_binance_futures_rest.py
python check_binance_futures_ws.py

Write-Host "Result: $scriptDir\f2_migration_check_result.json"
Write-Host "Report: $scriptDir\f2_migration_check_report.md"
