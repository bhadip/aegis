import os, json, time, httpx, feedparser
from datetime import datetime
from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from apscheduler.schedulers.background import BackgroundScheduler

app = FastAPI(title="AEGIS News Intelligence Agent")
analyzer = SentimentIntensityAnalyzer()

# Default Configurable Parameters - COMPLETE SET
news_config = {
    "default_keywords": [
        "Tariff", "Fed", "War", "Inflation", "Recession", "Nasdaq", 
        "CPI", "PPI", "FOMC", "Unemployment", "GDP", "Geopolitics", 
        "Oil", "Gold", "Interest Rate", "Powell", "China", "Trade",
        "Semiconductor", "AI", "Tech", "Earnings", "Market", "Stock"
    ],
    "active_keywords": [
        "Tariff", "Fed", "War", "Inflation", "Recession", "Nasdaq"
    ],
    "default_rss_feeds": [
        "https://feeds.bbci.co.uk/news/business/rss.xml",
        "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml",
        "https://feeds.finance.yahoo.com/rss/2.0/headline?s=^NDX&region=US&lang=en-US",
        "https://feeds.reuters.com/reuters/businessNews",
        "https://www.cnbc.com/id/100003114/device/rss/rss.html",
        "https://www.ft.com/rss/home/us",
        "https://feeds.bloomberg.com/markets/news.rss",
        "https://www.marketwatch.com/rss/marketpulse",
        "https://feeds.feedburner.com/zerohedge/feed",
        "https://www.investing.com/rss/news.rss"
    ],
    "active_rss_feeds": [
        "https://feeds.bbci.co.uk/news/business/rss.xml",
        "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml",
        "https://feeds.finance.yahoo.com/rss/2.0/headline?s=^NDX&region=US&lang=en-US"
    ],
    "risk_threshold_low": 40,
    "risk_threshold_high": 70
}

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
latest_scan = {"risk_score": 0, "bias": "Neutral/Caution", "primary_driver": "None", "recommendation": "Pending", "verified_sources": [], "scan_timestamp": datetime.utcnow().isoformat()}

class NewsConfigUpdate(BaseModel):
    active_keywords: list
    active_rss_feeds: list
    risk_threshold_low: int
    risk_threshold_high: int
    save_as_default: bool = False

class UrlValidationRequest(BaseModel):
    url: str

@app.post("/api/v1/news/validate_url")
def validate_url(req: UrlValidationRequest):
    try:
        # Try to parse the feed with timeout
        feed = feedparser.parse(req.url, request_headers=HEADERS)
        if len(feed.entries) > 0:
            return {"valid": True, "title": feed.feed.get("title", "Unknown Feed")}
        else:
            return {"valid": False, "error": "No entries found in feed"}
    except Exception as e:
        return {"valid": False, "error": f"Failed to parse: {str(e)}"}

@app.post("/api/v1/news/config")
def update_config(config: NewsConfigUpdate):
    global news_config
    news_config["active_keywords"] = config.active_keywords
    news_config["active_rss_feeds"] = config.active_rss_feeds
    news_config["risk_threshold_low"] = config.risk_threshold_low
    news_config["risk_threshold_high"] = config.risk_threshold_high
    if config.save_as_default:
        news_config["default_keywords"] = config.active_keywords.copy()
        news_config["default_rss_feeds"] = config.active_rss_feeds.copy()
    return {"status": "success", "config": news_config}

@app.get("/api/v1/news/config")
def get_config():
    return news_config

def perform_scan():
    global latest_scan, news_config
    articles = []
    for url in news_config["active_rss_feeds"]:
        try:
            feed = feedparser.parse(url, request_headers=HEADERS)
            for entry in feed.entries[:10]:
                articles.append({
                    "headline": entry.get("title", ""), 
                    "summary": entry.get("summary", entry.get("description", "")), 
                    "url": entry.get("link", ""), 
                    "publisher": feed.feed.get("title", "Unknown"), 
                    "published": entry.get("published", datetime.utcnow().isoformat())
                })
        except Exception as e: 
            print(f"Failed to parse {url}: {e}")

    scored_sources, total_score = [], 0
    matched_keywords_count = {k: 0 for k in news_config["active_keywords"]}
    for art in articles:
        text = f"{art['headline']} {art['summary']}".lower()
        matched = [k for k in news_config["active_keywords"] if k.lower() in text]
        if matched:
            vs = analyzer.polarity_scores(text)
            total_score += vs['compound']
            for k in matched: matched_keywords_count[k] += 1
            scored_sources.append({
                "headline": art['headline'], 
                "source_url": art['url'], 
                "publisher": art['publisher'], 
                "publish_timestamp": art['published'], 
                "matched_keywords": matched, 
                "individual_sentiment_score": round(vs['compound'], 4)
            })

    avg_score = total_score / len(scored_sources) if scored_sources else 0
    risk_score = max(0, min(100, int((0.5 - avg_score) * 100)))
    primary_driver = max(matched_keywords_count, key=matched_keywords_count.get) if any(matched_keywords_count.values()) else "None"
    
    low_t = news_config["risk_threshold_low"]
    high_t = news_config["risk_threshold_high"]
    
    if risk_score > high_t or avg_score < -0.5: 
        bias = "Bearish Bias"
        rec = f"⚠️ HIGH RISK ({bias}): Reduce Base Lot Size by 50%, Widen Grid Distance to 2x ATR, lower Max Floating Lots."
    elif risk_score > low_t or avg_score < 0: 
        bias = "Neutral/Caution"
        rec = f"⚡ MODERATE RISK ({bias}): Maintain Lot Size, but enable Dynamic ATR Grid Spacing."
    else: 
        bias = "Bullish Bias"
        rec = f"🟢 LOW RISK ({bias}): Parameters optimal. Consider increasing Base Lot Size by 20%."

    latest_scan = {
        "scan_timestamp": datetime.utcnow().isoformat(), 
        "risk_score": risk_score, 
        "bias": bias, 
        "primary_driver": primary_driver, 
        "recommendation": rec, 
        "verified_sources": sorted(scored_sources, key=lambda x: x['individual_sentiment_score'])[:5]
    }
    print(f"Scan Complete. Risk Score: {risk_score} ({bias})")

@app.get("/api/v1/news/scan")
def trigger_scan(background_tasks: BackgroundTasks):
    background_tasks.add_task(perform_scan)
    return {"status": "Scan initiated"}

@app.get("/api/v1/news/status")
def get_status(): 
    return latest_scan

scheduler = BackgroundScheduler()
scheduler.add_job(perform_scan, 'interval', hours=6)
scheduler.start()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
