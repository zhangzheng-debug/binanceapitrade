# New Server F2 Migration Checker

The fastest live path is not more dry-run time on a server where Binance Futures mainnet REST returns HTTP 451. Use the portable F2 checker on a candidate replacement server before deploying the full bot.

## Location

`tools/f2_migration_checker/`

## Run

```bash
cd tools/f2_migration_checker
bash run_f2_check.sh
```

Windows:

```powershell
cd tools\f2_migration_checker
.\run_f2_check.ps1
```

Outputs:

- `f2_migration_check_result.json`
- `f2_migration_check_report.md`

## Safety

The checker:

- uses public REST and public WebSocket endpoints only;
- does not read API keys;
- does not sign requests;
- does not place orders;
- does not use proxy, VPN, tunnel, or bypass behavior.

## Decisions

- `F2_MAINNET_REST_GO`: continue to signed read-only preflight planning.
- `F2_MAINNET_REST_NO_GO`: this server is not suitable for Binance Futures live.
- `TESTNET_ONLY_POSSIBLE_BUT_LIVE_NO_GO`: testnet may be separately evaluated, but live remains blocked.
- `PUBLIC_WS_DRY_RUN_ONLY`: WebSockets work but REST does not; do not treat this as live readiness.
- `NETWORK_ISSUE_DIAGNOSE`: fix DNS, TLS, timeout, or network issues before continuing.

If mainnet REST returns 451, choose a lawful server environment where Binance Futures REST is reachable. Do not try to bypass 451.
