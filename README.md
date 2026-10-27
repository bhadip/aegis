# ExaGuard AEGIS

**Autonomous Execution & Grid Intelligence System** - Version **0.3.9**

> Disclaimer: This is an experimental automated trading research system.
> Nothing here constitutes financial or investment advice. Automated trading carries substantial risk of loss.

## Architecture

| Component | Tech | Role |
|---|---|---|
| mt5_ea/AEGIS_Captain.mq5 | MQL5 (MetaTrader 5) | Execution engine: entries, exits, filters, status reporting |
| bridge/main.py | Python / FastAPI | Bridge API: config store, status aggregation, Telegram alerts, news orchestration, web hosting |
| news-agent/scanner.py | Python / FastAPI | RSS ingestion, keyword matching, VADER sentiment scoring |
| web-ui/ | Vue 2 + Tailwind (CDN) | Dashboard, News Intelligence, Settings (desktop and mobile) |

Data flow: EA <-> Bridge (5s poll/push) <-> Web UI (2s poll). Bridge -> News Agent (scan trigger + status). Bridge -> Telegram (alerts).

## Current Trading Logic (v0.3.9)

Full specification: docs/TRADING_LOGIC.md

- Long-only: sell/short positions are strictly prohibited.
- Entry gates (in order): Dashboard pause, MT5 Algo Trading, Margin Level >= 1000%, H1 RSI(14) >= Min H1 RSI (default 30), price not in top 15% of 4-week ATH/ATL range, lot-based exposure cap (Equity / Multiplier x 0.01).
- Trigger: RSI(14) hook on any of M1/M5/M15/M30 (current > previous, current < 40).
- Grid filter: new entry only >= Grid Distance (price points, default 100) from every open position.
- Exit: hard TP on ticket = entry + TP (price points). TP base by News Risk Score (20/15/10), halved when H1 RSI is 40-60. Optional basket close (default disabled).
- Units: TP and Grid Distance are price points. Exposure cap is lot-based.

## Dashboard and Alerts

- Live equity/balance/margin/status, ATH/ATL/pause-threshold, algo-trading state with explicit waiting reason.
- Pause/Resume synced across devices via 2s polling, data export/download, scan controls, keyword/RSS management, EA settings.
- Telegram: algo enable/disable plus reason changes, account status changes, scan completed/failed.

## Known Issues (open)

- News scan does not complete (v0.3.9): on-demand and scheduled scans stay in "Scanning..." state; no dashboard result and no Telegram summary. The async refactor with hard timeouts did not resolve it. See CHANGELOG.md "Known Issues". Trading logic is unaffected; EA falls back to Risk Score 50 when scan data is absent.

## Quick Start

```bash
cd ~/aegis
docker compose up -d --build
# MT5: compile AEGIS_Captain.mq5 (F7), attach to .ND H1 chart, enable Algo Trading
```

## Known Issues
- **Scan Analytics**: Currently under active troubleshooting. Data pipeline from MT5 to Bridge analytics is being investigated.
