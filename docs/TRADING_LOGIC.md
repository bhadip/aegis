# AEGIS Trading Logic - v0.3.9

## Scope and Safety Rules
- Instrument: .ND (Nasdaq 100), chart timeframe H1.
- Long-only. Market Buy is the sole order type. Pending orders and sells are prohibited.
- Cycle: config pull + status push every 5 s; decision logic once per minute.

## Entry Gates (evaluated in order; first failure stops the cycle)
1. User pause - Dashboard Pause flag (IS_PAUSED).
2. MT5 Algo Trading - terminal button must be enabled.
3. Margin safety - Margin Level >= 1000%.
4. H1 trend filter - if enabled, H1 RSI(14) >= MinH1RSI (default 30).
5. ATH/ATL percentile filter - 4-week window = 480 H1 bars.
   pause_threshold = ATL + (ATH - ATL) x (1 - threshold); threshold default 0.15 (top 15% blocked).
6. Lot-based exposure cap - open_lots + base_lot <= (Equity / EquityMultiplier) x 0.01
   (example: 10,000 USD / 2,500 -> max 0.04 lots).

## Entry Trigger
- RSI(14) hook on any of M1, M5, M15, M30: RSI_current > RSI_previous AND RSI_current < 40.
- Grid distance filter: if any position is open, abs(price - entry_i) >= GridDistance for every open position i. Grid Distance is in price points (default 100 = 100.00).
- Execution: Market Buy, lot = Base Lot (0.01), hard TP on ticket, comment tag AEGIS_MTF[tf]_RSI[x]_H1[y].

## Take-Profit (price points)
- Base by News Risk Score (0-100, pushed by Bridge): <40 -> TP_LOW (20), 40-70 -> TP_MED (15), >70 -> TP_HIGH (10).
- Adjustment: if H1 RSI in [40, 60] -> base x 0.5 (this is how TP_HIGH 10 naturally becomes 5).
- No other floors or caps. Hard TP price = entry + targetTP, normalized to symbol digits.

## Basket Close (default DISABLED since v0.3.9)
- If enabled: close all magic-number positions when average floating profit (price points) >= targetTP (same calculation as above).

## Status and Reason Reporting (since v0.3.8)
EA pushes every 5 s: equity, balance, margin level, positions, ATH, ATL, pause threshold, algo-allowed flag, and restriction_reason, which is one of:
User Paused; Algo Trading Disabled in MT5; Margin Level < 1000%; H1 RSI < min; Price in Top 15% of 4-Week Range; Waiting for Grid Distance (Current: X pts); Waiting for RSI Hook; Waiting for Initial RSI Hook; None.
The Dashboard renders this reason live (waiting / ready).

## News Pipeline
- Bridge triggers GET /api/v1/news/scan on the News Agent, then reads /api/v1/news/status.
- Risk Score = (1 - avg_sentiment) x 50, clamped 0-100. Bias: > +0.1 Bullish, < -0.1 Bearish, else Neutral.
- Result is pushed to the EA as RISK_SCORE and displayed with top-3 headlines.
- Status: BROKEN in v0.3.9 - see CHANGELOG.md Known Issues.

## Telegram Alerts
- Algo trading enabled/disabled (with reason), reason changes while restricted.
- Account status transitions (Very Safe / Safe / Warning).
- Scan completed (score, bias, top headlines) or scan failed (error).
