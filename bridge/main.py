import os
import json
import time
import httpx
import requests
import asyncio
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel

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

            risk_score = "N/A"
            bias = "N/A"
            sources_list = []
            sent_line = ""

            if isinstance(data, list) and len(data) > 0:
                sources_list = data
                scores = [a.get("individual_sentiment_score", 0) for a in data if "individual_sentiment_score" in a]
                if scores:
                    avg_sentiment = sum(scores) / len(scores)
                    risk_score = int((1 - avg_sentiment) * 50)
                    risk_score = max(0, min(100, risk_score))
                    if avg_sentiment > 0.1: bias = "Bullish"
                    elif avg_sentiment < -0.1: bias = "Bearish"
                    else: bias = "Neutral"
                    sent_line = f"\nAvg Sentiment: {avg_sentiment*100:.0f}%"
            elif isinstance(data, dict):
                risk_score = data.get("risk_score", data.get("score", "N/A"))
                bias = data.get("bias", data.get("sentiment", "N/A"))
                sources_list = data.get("verified_sources", data.get("sources", data.get("articles", [])))

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
                     g_hook: str = "", g_cur: float = 0.0, pos: str = "", last_action: str = ""):
    global account_status, ea_metrics
    new_status = "Disconnected"
    if margin_level > 2000: new_status = "Very Safe"
    elif margin_level > 1000: new_status = "Safe"
    elif margin_level > 0: new_status = "Warning"
    account_status = {"equity": equity, "balance": balance, "margin_level": margin_level, "active_positions": active_positions, "status": new_status}
    ea_metrics = {"ath": ath, "atl": atl, "threshold": threshold, "trade_allowed": bool(trade_allowed), "restriction_reason": restriction_reason, "grid_eff": grid_eff, "atr": atr,
                  "g_h1": g_h1, "g_h1min": g_h1min, "g_athpct": g_athpct, "g_lots": g_lots,
                  "g_lotmax": g_lotmax, "g_dist": g_dist, "g_need": g_need, "g_hook": g_hook,
                  "g_cur": g_cur, "pos": pos, "last_action": last_action}
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
async def trigger_scan():
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
def trigger_export(days: int = 30, price: str = "BID"):
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

app.mount("/static", StaticFiles(directory="web-ui"), name="static")

@app.get("/", response_class=HTMLResponse)
async def read_root():
    with open("web-ui/index.html", "r") as f: return f.read()
