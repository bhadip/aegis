import os
import json
import time
import httpx
import requests
import asyncio
from datetime import datetime, timezone, timedelta
import csv, bisect
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi import Depends, HTTPException
import jwt
import requests as req_lib
from typing import Optional
import hashlib
from pydantic import BaseModel





CLOUDFLARE_TEAM_DOMAIN = "delicate-brook-2c40.cloudflareaccess.com"
JWKS_URL = f"https://{CLOUDFLARE_TEAM_DOMAIN}/cdn-cgi/access/certs"
USERS_PATH = "/app/users.json"
SESSION_SECRET = os.getenv("SESSION_SECRET", "aegis-session-key-change-in-prod")
ACCESS_LOGOUT_URL = f"https://{CLOUDFLARE_TEAM_DOMAIN}/cdn-cgi/access/logout"

_jwks_cache = None
def get_jwks():
    global _jwks_cache
    if not _jwks_cache:
        _jwks_cache = __import__('requests').get(JWKS_URL, timeout=5).json()
    return _jwks_cache

def verify_jwt(token: str):
    import jwt
    try:
        jwks = get_jwks()
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")
        public_key = None
        for key in jwks.get("keys", []):
            if key["kid"] == kid:
                public_key = jwt.algorithms.RSAAlgorithm.from_jwk(__import__('json').dumps(key))
                break
        if not public_key:
            return None
        decoded = jwt.decode(token, public_key, algorithms=["RS256"], audience=jwks.get("audience", []))
        return decoded.get("email")
    except Exception as e:
        print(f"JWT verify failed: {e}")
        return None

def get_current_user(request):
    token = request.cookies.get("aegis_session")
    if token:
        email = verify_jwt(token)
        if email:
            import json
            users = json.load(open(USERS_PATH))
            for u in users["users"]:
                if u["email"] == email and u["enabled"]:
                    return u
    return None

def require_auth(request):
    user = get_current_user(request)
    if not user:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user

def require_admin(request):
    user = require_auth(request)
    if user["role"] != "admin":
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Admin required")
    return user


app = FastAPI(title="ExaGuard AEGIS Bridge API v0.7.1")

account_status = {"equity": 0.0, "balance": 0.0, "margin_level": 0.0, "active_positions": 0, "status": "Disconnected"}
ea_metrics = {"ath": 0.0, "atl": 0.0, "threshold": 0.0, "trade_allowed": True, "restriction_reason": "None"}
is_paused = False
last_scan_result = None
scan_in_progress = False
last_scan_time = None
ea_config = {
    "LOT": 0.01, "GRID_DISTANCE": 100.0, "EQUITY_MULTIPLIER": 2500,
    "RISK_SCORE": 50, "ENABLE_BASKET": "false",
    "IS_PAUSED": "false", "ATH_THRESHOLD": "0.15", "SCAN_INTERVAL_HOURS": 4, "EXPORT_REQUEST": "0", "EXPORT_DONE": "0", "EXPORT_DAYS": "30", "GRID_MIN": 50.0, "GRID_MAX": 300.0, "GRID_STEP_PCT": 25.0, "TP_MIN": 10.0, "TP_MAX": 100.0, "TP_T1_MULT": 0.6, "TP_TIER_STEP": 0.2, "TP_TIER_MAX": 1.4
}


DEFAULTS_PATH = "/app/mt5_ea/Files/aegis_config_default.json"
try:
    if os.path.exists(DEFAULTS_PATH):
        with open(DEFAULTS_PATH) as f:
            ea_config.update(json.load(f))
        print("Loaded persisted defaults from", DEFAULTS_PATH)
except Exception as e:
    print("Defaults load error:", e)

EA_PUBLIC_URL = os.getenv("EA_PUBLIC_URL", "http://100.75.220.84:9091")
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_telegram(msg):
    if TG_TOKEN and TG_CHAT_ID:
        try:
            requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
                          json={"chat_id": TG_CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=10)
        except Exception as e:
            print(f"Telegram error: {e}")

async def run_scan_logic():
    global last_scan_result, ea_config, scan_in_progress, last_scan_time
    scan_in_progress = True
    try:
        async with httpx.AsyncClient() as client:
            trigger_resp = await client.get("http://aegis-news:8000/api/v1/news/scan", timeout=45.0)
            trigger_resp.raise_for_status()

            status_resp = await client.get("http://aegis-news:8000/api/v1/news/status", timeout=15.0)
            status_resp.raise_for_status()
            data = status_resp.json()

            articles = []
            agent_risk = "N/A"
            agent_bias = "N/A"
            if isinstance(data, list):
                articles = data
            elif isinstance(data, dict):
                agent_risk = data.get("risk_score", data.get("score", "N/A"))
                agent_bias = data.get("bias", data.get("sentiment", "N/A"))
                articles = data.get("articles", data.get("verified_sources", data.get("sources", [])))
            if not isinstance(articles, list):
                articles = []
            seen = set()
            deduped = []
            for a in articles:
                if not isinstance(a, dict):
                    continue
                key = a.get("source_url") or a.get("headline") or ""
                if key in seen:
                    continue
                seen.add(key)
                deduped.append(a)
            scored = [a for a in deduped if isinstance(a.get("individual_sentiment_score"), (int, float))]
            if scored:
                avg_sentiment = sum(a["individual_sentiment_score"] for a in scored) / len(scored)
                risk_score = max(0, min(100, int((1 - avg_sentiment) * 50)))
                if avg_sentiment > 0.1:
                    bias = "Bullish"
                elif avg_sentiment < -0.1:
                    bias = "Bearish"
                else:
                    bias = "Neutral"
                sent_line = f"\nArticles scored: {len(scored)}\nAvg Sentiment: {avg_sentiment * 100:.0f}%"
                ea_config["SCAN_ARTICLES"] = str(len(scored))
                ea_config["SCAN_AVG_SENT"] = f"{avg_sentiment * 100:.0f}"
                ea_config["SCAN_BIAS"] = bias
                print(f"SCAN audit: n={len(scored)} avg={avg_sentiment:.4f} risk={risk_score} bias={bias}")
            else:
                risk_score = agent_risk
                bias = agent_bias
                sent_line = ""
                ea_config["SCAN_ARTICLES"] = "0"
                ea_config["SCAN_AVG_SENT"] = "0"
                ea_config["SCAN_BIAS"] = str(agent_bias)
                print("SCAN audit: no scored articles, used agent values:", agent_risk, agent_bias)
            ea_config["SCAN_ID"] = str(int(time.time()))
            from email.utils import parsedate_to_datetime
            import datetime as _dtm
            def _sort_key(item):
                idx, a = item
                try:
                    d = parsedate_to_datetime(a.get("publish_timestamp", ""))
                    if d is None:
                        return (1, 0.0, idx)
                    if d.tzinfo is None:
                        d = d.replace(tzinfo=_dtm.timezone.utc)
                    return (0, -d.timestamp(), idx)
                except Exception:
                    return (1, 0.0, idx)
            sources_list = [a for _, a in sorted(enumerate(deduped), key=_sort_key)]
            last_scan_result = {
                "risk_score": risk_score,
                "bias": (bias + " Bias") if (bias != "N/A" and not str(bias).endswith("Bias")) else bias,
                "sources": sources_list
            }
            last_scan_time = datetime.now(timezone.utc).isoformat()

            if risk_score != "N/A":
                ea_config["RISK_SCORE"] = str(risk_score)

            heads = [str(a.get('headline', a.get('title', 'N/A'))) for a in sources_list[:10]]
            def build_msg(hl):
                body = "\n".join([f"- {h}" for h in hl])
                return f"📰 *News Scan Completed*\nRisk Score: *{risk_score}/100*\nBias: *{bias}*{sent_line}\n\n*Headlines:*\n{body}"
            msg = build_msg(heads)
            while len(msg) > 4000 and heads:
                heads.pop()
                msg = build_msg(heads)
            send_telegram(msg)
    except Exception as e:
        last_scan_result = {"error": str(e)}
        last_scan_time = datetime.now(timezone.utc).isoformat()
        send_telegram(f"❌ *News Scan Failed*\nError: {str(e)}")
    finally:
        scan_in_progress = False

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(scan_scheduler())

async def scan_scheduler():
    elapsed = 0
    while True:
        await asyncio.sleep(60)
        elapsed += 60
        hours = float(ea_config.get("SCAN_INTERVAL_HOURS", 4))
        if elapsed >= hours * 3600:
            elapsed = 0
            await run_scan_logic()

class ConfigUpdate(BaseModel):
    base_lot_size: float; grid_distance: float; equity_multiplier: float
    enable_basket_close: bool = False
    ath_threshold: float = 0.15; scan_interval_hours: int = 4
    grid_min: float = 50.0; grid_max: float = 300.0; grid_step_pct: float = 25.0
    tp_min: float = 10.0; tp_max: float = 100.0
    tp_t1_mult: float = 0.6; tp_tier_step: float = 0.2; tp_tier_max: float = 1.4


@app.get("/api/v1/auth/me")
def auth_me(user: dict = Depends(require_auth)):
    return {"email": user["email"], "role": user["role"]}

@app.post("/api/v1/auth/logout")
def auth_logout(response: JSONResponse):
    response.delete_cookie("aegis_session")
    return {"status": "logged_out", "access_logout_url": ACCESS_LOGOUT_URL}

@app.get("/api/v1/admin/users")
def admin_list_users(user: dict = Depends(require_admin)):
    users = json.load(open(USERS_PATH))
    return users

@app.post("/api/v1/admin/users")
async def admin_add_user(request: Request, user: dict = Depends(require_admin)):
    data = await request.json()
    users = json.load(open(USERS_PATH))
    for u in users["users"]:
        if u["email"] == data["email"]:
            u["role"] = data["role"]
            u["enabled"] = data.get("enabled", True)
            json.dump(users, open(USERS_PATH, 'w'), indent=2)
            return {"status": "updated"}
    users["users"].append({"email": data["email"], "role": data["role"], "enabled": data.get("enabled", True)})
    json.dump(users, open(USERS_PATH, 'w'), indent=2)
    return {"status": "added"}

@app.delete("/api/v1/admin/users")
def admin_remove_user(email: str, user: dict = Depends(require_admin)):
    users = json.load(open(USERS_PATH))
    users["users"] = [u for u in users["users"] if u["email"] != email]
    json.dump(users, open(USERS_PATH, 'w'), indent=2)
    return {"status": "removed"}

@app.get("/api/v1/status")
def get_status():
    return {**account_status, **ea_metrics, "is_paused": is_paused,
            "last_scan_result": last_scan_result,
            "scan_in_progress": scan_in_progress,
            "last_scan_time": last_scan_time,
            "ea_config": ea_config}

@app.get("/api/v1/ea/status")
def update_ea_status(equity: float = 0.0, balance: float = 0.0, margin_level: float = 0.0, active_positions: int = 0,
                     ath: float = 0.0, atl: float = 0.0, threshold: float = 0.0, trade_allowed: int = 1,
                     restriction_reason: str = "None", grid_eff: float = 0.0, atr: float = 0.0,
                     g_h1: float = 0.0, g_h1min: float = 0.0, g_athpct: float = 0.0,
                     g_lots: float = 0.0, g_lotmax: float = 0.0, g_dist: float = 0.0, g_need: float = 0.0,
                     g_hook: str = "", g_cur: float = 0.0, pos: str = "", last_action: str = "",
                     ath_t: int = 0, atl_t: int = 0):
    global account_status, ea_metrics
    new_status = "Disconnected"
    if margin_level > 2000: new_status = "Very Safe"
    elif margin_level > 1000: new_status = "Safe"
    elif margin_level > 0: new_status = "Warning"
    account_status = {"equity": equity, "balance": balance, "margin_level": margin_level, "active_positions": active_positions, "status": new_status}
    ea_metrics = {"ath": ath, "atl": atl, "threshold": threshold, "trade_allowed": bool(trade_allowed), "restriction_reason": restriction_reason, "grid_eff": grid_eff, "atr": atr,
                  "g_h1": g_h1, "g_h1min": g_h1min, "g_athpct": g_athpct, "g_lots": g_lots,
                  "g_lotmax": g_lotmax, "g_dist": g_dist, "g_need": g_need, "g_hook": g_hook,
                  "g_cur": g_cur, "pos": pos, "last_action": last_action, "ath_t": ath_t, "atl_t": atl_t, "ea_url": EA_PUBLIC_URL}
    return {"status": "received"}

@app.get("/api/v1/control/pause")
def get_pause_status(): return {"is_paused": is_paused}

@app.post("/api/v1/control/pause")
def set_pause_status(paused: bool):
    global is_paused
    is_paused = paused
    ea_config["IS_PAUSED"] = str(paused).lower()
    return {"status": "success", "is_paused": is_paused}

@app.get("/api/v1/ea/config")
def get_ea_config():
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(content="\n".join([f"{k}={v}" for k, v in ea_config.items()]))

@app.post("/api/v1/config/update")
def update_config(config: ConfigUpdate):
    global ea_config
    ea_config["LOT"] = config.base_lot_size; ea_config["GRID_DISTANCE"] = config.grid_distance
    ea_config["EQUITY_MULTIPLIER"] = config.equity_multiplier
    ea_config["ENABLE_BASKET"] = str(config.enable_basket_close).lower()
    ea_config["ATH_THRESHOLD"] = str(config.ath_threshold); ea_config["SCAN_INTERVAL_HOURS"] = str(config.scan_interval_hours)
    ea_config["GRID_MIN"] = str(config.grid_min); ea_config["GRID_MAX"] = str(config.grid_max)
    ea_config["GRID_STEP_PCT"] = str(config.grid_step_pct)
    ea_config["TP_MIN"] = str(config.tp_min); ea_config["TP_MAX"] = str(config.tp_max)
    ea_config["TP_T1_MULT"] = str(config.tp_t1_mult); ea_config["TP_TIER_STEP"] = str(config.tp_tier_step)
    ea_config["TP_TIER_MAX"] = str(config.tp_tier_max)
    return {"status": "success"}

@app.api_route("/api/v1/news/scan", methods=["GET", "POST"])
async def trigger_scan(user: dict = Depends(require_auth)):
    # Fire-and-forget: acknowledge immediately, scan runs in background
    if scan_in_progress:
        return {"status": "already_running"}
    asyncio.create_task(run_scan_logic())
    return {"status": "scan_started"}

@app.get("/api/v1/news/config")
async def get_news_config():
    return {
        "default_keywords": ["Fed", "ECB", "inflation", "CPI", "NFP", "unemployment", "GDP", "interest rate", "tariff", "trade war", "war", "conflict", "sanctions", "oil", "energy"],
        "active_keywords": ["Fed", "ECB", "inflation", "CPI", "NFP", "unemployment", "GDP", "interest rate", "tariff", "trade war"],
        "default_rss_feeds": ["https://feeds.bbci.co.uk/news/business/rss.xml", "https://rss.cnn.com/rss/money_latest.rss", "https://www.reutersagency.com/feed/", "https://www.cnbc.com/id/100003114/device/rss/rss.html"],
        "active_rss_feeds": ["https://feeds.bbci.co.uk/news/business/rss.xml", "https://rss.cnn.com/rss/money_latest.rss"]
    }

@app.api_route("/api/v1/tools/export", methods=["GET", "POST"])
def trigger_export(user: dict = Depends(require_auth), days: int = 30, price: str = "BID"):
    file_path = "/app/mt5_ea/Files/data_export.csv"
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, 'w') as f:
        f.write("")
    ea_config["EXPORT_DAYS"] = str(days)
    ea_config["EXPORT_PRICE"] = price.upper() if price.upper() in ("BID", "ASK") else "BID"
    ea_config["EXPORT_DONE"] = "0"
    ea_config["EXPORT_REQUEST"] = str(int(time.time()))
    return {"status": "export_requested", "days": days, "id": ea_config["EXPORT_REQUEST"]}

@app.post("/api/v1/tools/export_chunk")
async def export_chunk(request: Request):
    body = await request.body()
    with open("/app/mt5_ea/Files/data_export.csv", "ab") as f:
        f.write(body)
    return {"status": "ok"}

@app.api_route("/api/v1/tools/export_done", methods=["GET", "POST"])
def export_done(id: str = "0"):
    if id == ea_config.get("EXPORT_REQUEST", "0"):
        ea_config["EXPORT_DONE"] = id
    return {"status": "ok"}

@app.get("/api/v1/tools/export_status")
def check_export_status():
    req = ea_config.get("EXPORT_REQUEST", "0")
    done = ea_config.get("EXPORT_DONE", "0")
    ready = req != "0" and req == done and os.path.exists("/app/mt5_ea/Files/data_export.csv")
    state = "ready" if ready else ("idle" if req == "0" else ("streaming" if done == "0" else "done_no_file"))
    return {"ready": ready, "state": state, "request": req, "done": done}

@app.post("/api/v1/config/save_default")
def save_default():
    with open(DEFAULTS_PATH, "w") as f:
        json.dump(ea_config, f, indent=2)
    return {"status": "saved", "path": DEFAULTS_PATH}

@app.get("/api/v1/tools/download_data")
def download_data():
    file_path = "/app/mt5_ea/Files/data_export.csv"
    if os.path.exists(file_path): return FileResponse(file_path, media_type='text/csv', filename='aegis_data_export.csv')
    raise HTTPException(status_code=404, detail="No exported data found.")


LOG_PATH = "/app/mt5_ea/Files/score_log.csv"
DIST_NEED = 50
ACC_NEED = 100

def _read_log():
    rows = []
    if not os.path.exists(LOG_PATH):
        return rows
    with open(LOG_PATH, newline='') as f:
        for row in csv.DictReader(f):
            try:
                row['ts'] = datetime.strptime(row['timestamp'], '%Y.%m.%d %H:%M:%S')
                row['bid'] = float(row['bid']); row['risk_score'] = float(row['risk_score'])
                rows.append(row)
            except Exception:
                continue
    return rows

def _pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return None
    mx = sum(xs) / n; my = sum(ys) / n
    sx = sum((x - mx) ** 2 for x in xs) ** 0.5; sy = sum((y - my) ** 2 for y in ys) ** 0.5
    if sx == 0 or sy == 0:
        return None
    return round(sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (sx * sy), 3)

@app.get("/api/v1/analytics/summary")
def analytics_summary(window: str = "7d"):
    rows = _read_log()
    now = datetime.now()
    cutoff = now - timedelta(days=7 if window == "7d" else (30 if window == "30d" else 36500))
    sel = [r for r in rows if r['ts'] >= cutoff]
    out = {"window": window, "have": len(sel),
           "progress": {"dist": f"{len(sel)}/{DIST_NEED}", "acc": ""},
           "distribution_ready": len(sel) >= DIST_NEED, "accuracy_ready": False,
           "stats": None, "histogram": [], "dist_max": 1, "by_hour": [],
           "correlations": {"h1": None, "h4": None, "h24": None, "vol": None},
           "bias_accuracy": None}
    scores = [r['risk_score'] for r in sel]
    if len(sel) >= DIST_NEED:
        so = sorted(scores)
        q = lambda p: so[min(len(so) - 1, int(p * len(so)))]
        out["stats"] = {"mean": round(sum(scores) / len(scores), 1), "median": q(0.5),
                        "std": round((sum((x - sum(scores)/len(scores))**2 for x in scores)/len(scores)) ** 0.5, 1),
                        "min": so[0], "max": so[-1], "p25": q(0.25), "p75": q(0.75), "p90": q(0.9)}
        hist = [{"bin": f"{b}-{b+10}", "count": sum(1 for x in scores if b <= x < b + 10)} for b in range(0, 100, 10)]
        out["histogram"] = hist
        out["dist_max"] = max(1, max(h["count"] for h in hist))
        hours = {}
        for r in sel:
            hours.setdefault(r['ts'].hour, []).append(r['risk_score'])
        out["by_hour"] = [{"hour": h, "mean": round(sum(v)/len(v), 1), "n": len(v)} for h, v in sorted(hours.items())]
    pts = sorted([(r['ts'], r['bid'], r['risk_score'], r['bias']) for r in sel])
    tsl = [p[0] for p in pts]
    def fwd(i, hours):
        target = pts[i][0] + timedelta(hours=hours)
        j = bisect.bisect_left(tsl, target)
        if j >= len(pts) or pts[j][0] > target + timedelta(hours=max(2, hours // 2)):
            return None
        return (pts[j][1] - pts[i][1]) / pts[i][1] * 100.0
    pairs = {1: [], 4: [], 24: []}
    for i in range(len(pts)):
        age_h = (now - pts[i][0]).total_seconds() / 3600.0
        for h in (1, 4, 24):
            if age_h >= h + 0.5:
                f = fwd(i, h)
                if f is not None:
                    pairs[h].append((pts[i][2], f, pts[i][3]))
    out["progress"]["acc"] = f"{len(pairs[4])}/{ACC_NEED}"
    if len(pairs[4]) >= ACC_NEED:
        out["accuracy_ready"] = True
        out["correlations"] = {
            "h1": _pearson([p[0] for p in pairs[1]], [p[1] for p in pairs[1]]),
            "h4": _pearson([p[0] for p in pairs[4]], [p[1] for p in pairs[4]]),
            "h24": _pearson([p[0] for p in pairs[24]], [p[1] for p in pairs[24]]),
            "vol": _pearson([p[0] for p in pairs[4]], [abs(p[1]) for p in pairs[4]])}
        bull = [p for p in pairs[4] if p[2] == "Bullish"]; bear = [p for p in pairs[4] if p[2] == "Bearish"]
        neut = [p for p in pairs[4] if p[2] == "Neutral"]
        pct = lambda arr, fn: round(100.0 * sum(1 for p in arr if fn(p)) / len(arr), 1) if arr else None
        out["bias_accuracy"] = {"bullish_pct": pct(bull, lambda p: p[1] > 0), "bearish_pct": pct(bear, lambda p: p[1] < 0),
                                "neutral_flat_pct": pct(neut, lambda p: abs(p[1]) < 0.25),
                                "n_bull": len(bull), "n_bear": len(bear), "n_neut": len(neut)}
    return out

@app.get("/api/v1/analytics/download")
def analytics_download():
    if os.path.exists(LOG_PATH):
        return FileResponse(LOG_PATH, media_type='text/csv', filename='score_log.csv')
    raise HTTPException(status_code=404, detail='No log yet')

app.mount("/static", StaticFiles(directory="web-ui"), name="static")

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    user = get_current_user(request)
    with open("web-ui/index.html", "r") as f: html = f.read()
    if user:
        html = html.replace('__USER_EMAIL__', user["email"]).replace('__USER_ROLE__', user["role"])
    else:
        html = html.replace('__USER_EMAIL__', '').replace('__USER_ROLE__', '')
    return html
