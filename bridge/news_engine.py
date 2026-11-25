import os, json, time, threading, requests
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter

BASE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE, "scan_config.json")
STALE_PATH = os.path.join(BASE, "stale_state.json")
EVENTS_CACHE_PATH = os.path.join(BASE, "events_cache.json")
STORE_PATH = os.path.join(BASE, "events_store.json")

def cur_now():
    return datetime.now(timezone.utc)
def _load_store():
    try:
        with open(STORE_PATH) as f: return json.load(f)
    except Exception: return []
def _save_store(lst):
    with open(STORE_PATH,"w") as f: json.dump(lst, f)
FF_URLS = ["https://nfs.faireconomy.media/ff_calendar_thisweek.json", "https://cdn-nfs.faireconomy.media/ff_calendar_thisweek.json"]
SGT = timezone(timedelta(hours=8))
UA = {"User-Agent": "Mozilla/5.0"}

router_events = APIRouter()
router_admin = APIRouter()

_ff_cache = {"ts": 0.0, "events": []}
_lock = threading.Lock()

def load_config():
    try:
        with open(CONFIG_PATH) as f: return json.load(f)
    except Exception:
        return {"active_profile": "ND100", "global": {}, "profiles": {}}

def save_config(cfg):
    with open(CONFIG_PATH, "w") as f: json.dump(cfg, f, indent=2)

def get_stale(profile):
    try:
        st = json.load(open(STALE_PATH)) if os.path.exists(STALE_PATH) else {}
        p = st.get(profile, {})
        if not p.get("last_unique_ts"): return {"stale": False, "hours": 0}
        hrs = (time.time() - p["last_unique_ts"]) / 3600.0
        return {"stale": hrs >= 1.0, "hours": round(hrs, 1)}
    except Exception:
        return {"stale": False, "hours": 0}

def record_stale(profile, articles_hash):
    try:
        st = json.load(open(STALE_PATH)) if os.path.exists(STALE_PATH) else {}
    except Exception:
        st = {}
    p = st.get(profile, {})
    now = time.time()
    if p.get("hash") != articles_hash:
        p["hash"] = articles_hash
        p["last_unique_ts"] = now
    p["last_scan_ts"] = now
    st[profile] = p
    with open(STALE_PATH, "w") as f: json.dump(st, f)

def fetch_events():
    now = time.time()
    # Load cache
    try:
        with open(EVENTS_CACHE_PATH) as f: cache = json.load(f)
    except Exception: cache = {"ts": 0, "events": []}
    
    # Fetch fresh if cache is old (>15 mins)
    if now - cache["ts"] > 900:
        fresh = []
        for u in FF_URLS:
            try:
                r = requests.get(u, headers=UA, timeout=15)
                if r.status_code == 200:
                    for e in r.json():
                        if e.get("impact") == "High" and e.get("country") == "USD":
                            fresh.append({"title": e.get("title",""), "time": e.get("date",""),
                                         "forecast": e.get("forecast",""), "previous": e.get("previous",""),
                                         "actual": e.get("actual","")})
                    break
            except Exception: continue
        # Merge cache with fresh
        byk = {(e["time"]+"|"+e["title"]): e for e in cache["events"]}
        for e in fresh: byk[e["time"]+"|"+e["title"]] = e
        # Filter to last 7 days
        cut = datetime.now(timezone.utc) - timedelta(days=7)
        def _p(t):
            try: return datetime.fromisoformat(t)
            except: return None
        merged = [v for v in byk.values() if (_p(v["time"]) or datetime.now(timezone.utc)) > cut]
        merged.sort(key=lambda x: x["time"])
        cache = {"ts": now, "events": merged}
        with open(EVENTS_CACHE_PATH, "w") as f: json.dump(cache, f)
    
    evs = cache["events"]
    cur = datetime.now(timezone.utc)
    def parse(t):
        try: return datetime.fromisoformat(t)
        except: return None
    up = [e for e in evs if (parse(e["time"]) or cur) > cur]
    pa = [e for e in evs if (parse(e["time"]) or cur) <= cur]
    
    # Format upcoming
    next_events = []
    for e in up[:5]:
        dt = parse(e["time"]); d = dt - cur
        mins = int(d.total_seconds()//60); dd, rem = divmod(mins,1440); hh, mm = divmod(rem,60)
        parts = []
        if dd: parts.append(str(dd)+"d")
        if hh: parts.append(str(hh)+"h")
        parts.append(str(mm)+"m")
        ne = dict(e); ne["label"] = " ".join(parts) + " to " + e["title"]
        ne["time_sgt"] = dt.astimezone(SGT).strftime("%Y-%m-%d %H:%M")
        next_events.append(ne)
    
    # Format past
    past_events = []
    for e in pa[-5:]:
        dt = parse(e["time"]); mins = int((cur-dt).total_seconds()//60)
        pe = dict(e)
        if mins < 60: pe["label"] = str(mins) + " mins past " + e["title"]
        elif mins < 1440: pe["label"] = str(mins//60) + " hours past " + e["title"]
        else: pe["label"] = str(mins//1440) + " days past " + e["title"]
        pe["time_sgt"] = dt.astimezone(SGT).strftime("%Y-%m-%d %H:%M")
        past_events.append(pe)
    
    out_up = next_events[0] if next_events else None
    out_pa = past_events[-1] if past_events else None
    
    return {"upcoming": out_up, "past": out_pa, "next_events": next_events, "past_events": past_events, "calendar_ok": bool(evs)}

@router_events.get("/api/v1/events")
def api_events(): return fetch_events()

def profile_payload():
    cfg = load_config(); name = cfg.get("active_profile","ND100")
    p = cfg.get("profiles",{}).get(name,{})
    return {"active_profile": name, "profiles": list(cfg.get("profiles",{}).keys()),
            "default_keywords": p.get("default_keywords",[]), "active_keywords": p.get("active_keywords",[]),
            "custom_keywords": p.get("custom_keywords",[]), "auto_keywords": p.get("auto_keywords",[]),
            "default_rss_feeds": p.get("default_feeds",[]), "active_rss_feeds": p.get("active_feeds",[]),
            "custom_feeds": p.get("custom_feeds",[]), 
            "schedule_hours": p.get("schedule_hours",4),
            "busy_hours_start_sgt": p.get("busy_hours_start_sgt",16),
            "busy_hours_end_sgt": p.get("busy_hours_end_sgt",5),
            "busy_interval_mins": p.get("busy_interval_mins",30),
            "quiet_interval_mins": p.get("quiet_interval_mins",180),
            "global": cfg.get("global",{}), "stale": get_stale(name)}

def save_profile_payload(data, role):
    cfg = load_config(); name = data.get("active_profile", cfg.get("active_profile","ND100"))
    cfg["active_profile"] = name; p = cfg["profiles"].setdefault(name, {})
    p["active_keywords"] = data.get("active_keywords", p.get("active_keywords", []))
    p["active_feeds"] = data.get("active_rss_feeds", p.get("active_feeds", []))
    if "schedule_hours" in data: p["schedule_hours"] = data["schedule_hours"]
    if "busy_hours_start_sgt" in data: p["busy_hours_start_sgt"] = data["busy_hours_start_sgt"]
    if "busy_hours_end_sgt" in data: p["busy_hours_end_sgt"] = data["busy_hours_end_sgt"]
    if "busy_interval_mins" in data: p["busy_interval_mins"] = data["busy_interval_mins"]
    if "quiet_interval_mins" in data: p["quiet_interval_mins"] = data["quiet_interval_mins"]
    if role == "admin":
        p["default_keywords"] = data.get("default_keywords", p.get("default_keywords", []))
        p["custom_keywords"] = data.get("custom_keywords", p.get("custom_keywords", []))
        p["default_feeds"] = data.get("default_rss_feeds", p.get("default_feeds", []))
        p["custom_feeds"] = data.get("custom_feeds", p.get("custom_feeds", []))
        g = cfg.get("global", {})
        for k in ["event_telegram_alert_mins","event_dashboard_past_mins"]:
            if k in data: g[k] = data[k]
        cfg["global"] = g
    save_config(cfg); return {"status":"saved","profile":name}

@router_admin.get("/api/v1/news/config")
def api_get_config(): return profile_payload()

@router_admin.post("/api/v1/news/config")
def api_save_config(data: dict, user: dict = None): return save_profile_payload(data, "admin")

@router_admin.post("/api/v1/news/profile")
def api_switch_profile(data: dict):
    cfg = load_config(); name = data.get("active_profile","ND100")
    if name in cfg.get("profiles",{}):
        cfg["active_profile"] = name; save_config(cfg); return {"status":"switched"}
    return {"status":"unknown_profile"}

def _load_ledger():
    try:
        with open(os.path.join(BASE, "event_alerts_sent.json")) as f: return json.load(f)
    except Exception: return {"pre":[], "release":[]}
def _save_ledger(l):
    with open(os.path.join(BASE, "event_alerts_sent.json"),"w") as f: json.dump(l, f)

def tg_send(text):
    tok = os.getenv("TELEGRAM_BOT_TOKEN"); chat = os.getenv("TELEGRAM_CHAT_ID")
    if not tok or not chat: return
    try:
        requests.post("https://api.telegram.org/bot"+tok+"/sendMessage",
                      json={"chat_id": chat, "text": text}, timeout=8)
    except Exception: pass

def alert_tick():
    cfg = load_config(); A = int(cfg.get("global",{}).get("event_telegram_alert_mins",15))
    evs = _ff_cache["events"]
    now = datetime.now(timezone.utc); led = _load_ledger(); changed=False
    for e in evs:
        try: dt = datetime.fromisoformat(e["time"])
        except Exception: continue
        key = e["time"]+"|"+e["title"]; d = (dt-now).total_seconds()
        if 0 < d <= A*60 and key not in led["pre"]:
            led["pre"].append(key); changed=True; tg_send(str(A)+" mins to "+e["title"])
        if -120 <= d <= 0 and key not in led["release"]:
            led["release"].append(key); changed=True; tg_send(e["title"]+" is being released")
    if changed: _save_ledger(led)

def scan_tick():
    cfg = load_config()
    st = {}
    try: st = json.load(open(STALE_PATH)) if os.path.exists(STALE_PATH) else {}
    except Exception: st = {}
    now = time.time()
    for name, p in cfg.get("profiles",{}).items():
        h = datetime.now(SGT).hour
        start = int(p.get("busy_hours_start_sgt", 16))
        end = int(p.get("busy_hours_end_sgt", 5))
        active = (h >= start or h < end) if start > end else (start <= h < end)
        interval = int(p.get("busy_interval_mins", 30) if active else p.get("quiet_interval_mins", 180)) * 60
        last = st.get(name,{}).get("last_scan_ts",0)
        if now - last >= interval:
            try:
                requests.post("http://127.0.0.1:8000/api/v1/internal/scan/"+name, timeout=60)
            except Exception: pass

def _loop():
    while True:
        try:
            fetch_events(); alert_tick(); scan_tick()
        except Exception as e:
            print("engine loop err:", e)
        time.sleep(30)

def start_engine():
    t = threading.Thread(target=_loop, daemon=True); t.start()
