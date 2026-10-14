# Changelog

## 0.4.0
- Dynamic Grid Distance: Grid = clamp(ATR_H1(14) x (0.60 + 0.80 x RiskScore/100), GridMin 50, GridMax 300) price points. Static value remains as fallback.
- Tiered volatility TP per position: TP(tier) = clamp(ATR_H1(14) x TierMult x (1.40 - 0.80 x RiskScore/100), TPMin 5, TPMax 100); TierMult = 1.00 / 0.75 / 0.60 / 0.50 for tiers 1/2/3/4+. Higher risk score lowers TP.
- Obsolete TP Low/Med/High settings removed from Bridge and Settings UI; EA inputs now own grid/TP tuning.
- Scan detail: Dashboard lists ALL verified sources with publisher, timestamp, keywords, sentiment and URL (scrollable, mobile-friendly).
- Telegram scan messages now contain complete headlines (no truncation), guarded to Telegram's 4096-char limit by dropping whole items only.
- Bugfixes carried from 0.3.10: export endpoint accepts POST; missing getSources() method restored (fixed frozen News tab and stuck "Scanning..." state); live config sync across PC/mobile.
- Dashboard compliance redesign: PROPOSED, pending user approval (not implemented).

## 0.3.9 (current)
- Scan made asynchronous: /api/v1/news/scan acknowledges immediately; scan runs as a background task.
- scan_in_progress + last_scan_time exposed on /api/v1/status; UI clears "Scanning..." via 2 s polling (8 s grace, 240 s hard cap).
- Hard timeouts on all outbound calls: News Agent scan 45 s, status 15 s, Telegram 10 s.
- Structured scan result (risk_score, bias, sources) with headline extraction in UI.
- Basket Close default changed to disabled.
- Cache-busting on static assets.

## 0.3.8
- EA now reports precise waiting reasons (grid distance with live distance, RSI hook states); Dashboard shows them instead of a generic "operational" message.
- Bridge news parser hardened for list- and dict-shaped agent responses.

## 0.3.7
- Bugfix release (version policy: bugfixes only).
- Fixed MQL5 compile errors (missing globals IsTradingPaused, CurrentRiskScore).
- Basket Close reduced to a single Enable/Disable toggle; TP parameters follow main EA settings.
- Removed arbitrary MinTP floor; the 50% H1-RSI reduction rule is the only adjustment.
- Bridge computes Risk Score/Bias from article sentiment and pushes RISK_SCORE to the EA.

## 0.3.6
- Hard Take-Profit placed on every ticket at entry, in price points (entry + TP).
- Grid Distance and TP unified to price points; Grid Distance default 100.
- Exposure cap changed from position count to total lot size.
- Long-only rule codified in EA comments and logic.

## Known Issues (open)

### News scan never completes (observed through 0.3.9)
- Symptom: "Run Scan Now" stays in "Scanning..."; no dashboard result; no Telegram summary. Scheduled scans likewise produce nothing.
- Not yet resolved by: async refactor, timeouts, structured parsing, cache-busting (0.3.9).
- Hypotheses:
  1. News Agent GET /api/v1/news/scan blocks or deadlocks internally (single-worker event loop blocked by synchronous feed fetching).
  2. /api/v1/news/status returns a shape the parser treats as empty after a fresh trigger (scan state reset before read).
  3. Background task exception path not reaching finally under container restarts.
- Diagnostics to run next:
```bash
docker logs aegis-news --tail 100
docker logs aegis-bridge --tail 100
time docker exec aegis-bridge python -c "import httpx; r=httpx.get('http://aegis-news:8000/api/v1/news/scan', timeout=120); print(r.status_code, r.text[:300])"
```
- Workaround: none; EA safely defaults to Risk Score 50 (TP_MED) when scan data is absent. Trading logic unaffected.
