import os, socket, time, requests, httpx, json
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from dotenv import load_dotenv
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, PlainTextResponse

load_dotenv()
app = FastAPI(title="ExaGuard AEGIS Bridge API")

# In-memory config & status storage
ea_config = {
    "LOT": 0.01,
    "GRID_DISTANCE": 50,
    "EQUITY_MULTIPLIER": 2500,
    "TP_LOW_RISK": 20,
    "TP_MED_RISK": 15,
    "TP_HIGH_RISK": 10
}
account_status = {"equity": 0, "balance": 0, "margin_level": 0, "status": "Disconnected", "active_positions": 0}

class ConfigUpdate(BaseModel):
    base_lot_size: float
    grid_distance: int
    equity_multiplier: float
    tp_low_risk: int
    tp_med_risk: int
    tp_high_risk: int

class EAStatusUpdate(BaseModel):
    equity: float
    balance: float
    margin_level: float
    active_positions: int

    class Config:
        extra = 'allow'  # Allow extra fields

from fastapi import Request

@app.get("/api/v1/ea/status")
def update_ea_status(equity: float = 0, balance: float = 0, margin_level: float = 0, active_positions: int = 0):
    global account_status
    account_status = {
        "equity": equity,
        "balance": balance,
        "margin_level": margin_level,
        "active_positions": active_positions,
        "status": "Disconnected"
    }
    if margin_level > 2000: account_status["status"] = "Very Safe"
    elif margin_level > 1000: account_status["status"] = "Safe"
    elif margin_level > 0: account_status["status"] = "Warning"
    return {"status": "received"}

@app.get("/api/v1/status")
def get_status():
    return account_status

@app.get("/api/v1/ea/config")
def get_ea_config():
    config_str = "\n".join([f"{k}={v}" for k, v in ea_config.items()])
    return PlainTextResponse(content=config_str)

@app.post("/api/v1/config/update")
def update_config(config: ConfigUpdate):
    global ea_config
    ea_config["LOT"] = config.base_lot_size
    ea_config["GRID_DISTANCE"] = config.grid_distance
    ea_config["EQUITY_MULTIPLIER"] = config.equity_multiplier
    ea_config["TP_LOW_RISK"] = config.tp_low_risk
    ea_config["TP_MED_RISK"] = config.tp_med_risk
    ea_config["TP_HIGH_RISK"] = config.tp_high_risk
    return {"status": "success", "message": "Config updated"}

app.mount("/static", StaticFiles(directory="web-ui"), name="static")

@app.get("/", response_class=HTMLResponse)
async def read_root():
    with open("web-ui/index.html", "r") as f:
        return f.read()

@app.api_route("/api/v1/news/{path:path}", methods=["GET", "POST"])
async def proxy_news(request: Request, path: str):
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.request(method=request.method, url=f"http://aegis-news:8000/api/v1/news/{path}", 
                                        params=request.query_params, json=await request.json() if request.method == "POST" else None, timeout=10.0)
            return resp.json()
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"News Agent unreachable: {str(e)}")
