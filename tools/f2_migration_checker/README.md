# F2 Migration Checker

Copy this directory to a candidate server and run:

```bash
bash run_f2_check.sh
```

or on Windows:

```powershell
.\run_f2_check.ps1
```

The checker uses public Binance Futures REST and WebSocket endpoints only. It does not read API keys, sign requests, place orders, or use proxy/VPN/tunnel bypass behavior.

Outputs:

- `f2_migration_check_result.json`
- `f2_migration_check_report.md`

Decision codes:

- `F2_MAINNET_REST_GO`: all checked mainnet public REST endpoints returned 2xx.
- `F2_MAINNET_REST_NO_GO`: one or more mainnet public REST endpoints returned HTTP 451.
- `TESTNET_ONLY_POSSIBLE_BUT_LIVE_NO_GO`: testnet/demo public REST is OK while mainnet public REST is 451.
- `PUBLIC_WS_DRY_RUN_ONLY`: public WebSockets work while mainnet public REST is 451.
- `NETWORK_ISSUE_DIAGNOSE`: DNS, TLS, timeout, or other network failures need diagnosis.

If mainnet REST returns 451, the server is not suitable for Binance Futures live. Do not use proxy, VPN, tunnel, or other bypass methods. Choose a lawful server environment where Binance Futures REST is reachable.
