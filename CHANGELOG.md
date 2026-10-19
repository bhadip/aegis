# Changelog

## 0.12.0
- Cloudflare Access integration: Bridge verifies CF_Authorization JWT (signed by Cloudflare JWKS) to identify authenticated users; session cookie tracks login state across requests.
- Role-based access control: users.json defines Admin (bhadip@gmail.com) and Fund Manager (tom@prasanti.com) roles; Admin-only User Management tab (add/update/remove users, enable/disable).
- Login/logout flow: /api/v1/auth/me checks session; logout clears Bridge session and redirects to Cloudflare Access logout URL.
- Protected routes: analytics, config updates, scan trigger, export, pause control now require valid session; EA status/config endpoints remain public (private network only).
- UI: role display in header, logout button, User Management tab (Admin only), auto-redirect to Access login if no session.
- Cloudflare Access apps created: aegis.prasanti.com (web) and ea-aegis.prasanti.com (VNC) with "registered-users" policy.

## 0.11.0
- Web app host port changed 8000 -> 9191 (container-internal 8000 unchanged); EA serverURL updated; 10-instance port scheme documented (web 9190+i, VNC 9090+i).
- Exposure cap now visible: Rule Compliance Exposure chip turns red with "cap: 0.04+0.01 > 0.0488" and the Algo Trading Status card shows the waiting reason, so a new user can see why entries stop at max positions.
- Dashboard shows when 4-week ATH and ATL were reached (H1 bar time) and the Range (ATH-ATL), making Pause Threshold = ATL + Range x 85% fully verifiable.
- Dashboard quick-link "Open MT5 Terminal (VNC)" (EA_PUBLIC_URL env, default http://100.75.220.84:9091) so Fund Managers need only the web URL.

## 0.10.0
- Includes the previously undeployed v0.9.2 scan-consistency fixes (single-source risk computation, dedup, recency-sorted headlines, Articles-scored/Avg-Sentiment in Telegram and logs).
- EA logs one row per scan to mt5_ea/Files/score_log.csv (timestamp, scan_id, risk, bias, articles, avg sentiment, bid, H1 ATR).
- Bridge analytics endpoints /api/v1/analytics/summary and /download; sufficiency-gated: distribution at 50 scans, accuracy at 100 aged forward-return pairs (1h/4h/24h horizons computed only from later logged bids, never future data).
- New Analytics tab: window selector, histogram, percentiles, bias hit-rates, score-vs-return and score-vs-volatility correlations, raw CSV download.

## 0.6.0
- Compile fix: SendChunk header string escape corrected (literal backslash-r-n), resolving "closing quote expected" errors at lines 123-125.
- Formula coefficients now configurable from Dashboard Settings (Formula Tuning section) and synced to the EA every 5 s: GRID_MIN, GRID_MAX, GRID_STEP_PCT, TP_MIN, TP_MAX, TP_T1_MULT, TP_TIER_STEP, TP_TIER_MAX.
- Defaults: TP range clamped to 10-100 price points (TP_MIN=10, TP_MAX=100).
- Preset example for gradual grid P1-P2 >= 99 and P4-P5 >= 250: set Grid Min = 99 and Grid Step % = 51 (99 x (1 + 3 x 0.51) = 250.5).

## 0.5.0
- Tiered TP INVERTED per user logic: TierMult = min(0.60 + 0.20 x (tier-1), 1.40); tier 1 (highest/worst entry) gets the smallest TP to clear floating fast; deepest tier gets the largest TP to ride the rebound.
- Gradual Grid Distance: required gap for the next position = GridBase x (1 + GridStepPct/100 x (openCount-1)), default step 25%, so P1-P2 < P2-P3 < P3-P4 ...
- Real history export: EA streams OHLCV + RSI14 + ATR14 for M1/M5/M15/M30/H1/D1 over the requested days in chunks to the Bridge; Download CSV now contains the full dataset (tens of thousands of rows for 1 month), not a stub.
- Settings: "Save as New Default" persists current config to mt5_ea/Files/aegis_config_default.json; Bridge reloads it on every start, so saved config survives restarts and rebuilds.
- Scan card now shows a Headlines list plus the full verified-sources detail; headline binding no longer depends on a helper method.

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
