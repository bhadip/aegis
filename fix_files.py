import os

os.makedirs('news-agent', exist_ok=True)

# 1. News Agent Dockerfile
with open('news-agent/Dockerfile', 'w') as f:
    f.write("""FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "scanner.py"]
""")

# 2. News Agent Requirements
with open('news-agent/requirements.txt', 'w') as f:
    f.write("""feedparser==6.0.10
vaderSentiment==3.3.2
apscheduler==3.10.4
requests==2.31.0
fastapi==0.109.0
uvicorn==0.27.0
httpx==0.27.0
""")

# 3. News Agent scanner.py
scanner_code = """import os
import json
import time
import httpx
import feedparser
from datetime import datetime
from fastapi import FastAPI, BackgroundTasks
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from apscheduler.schedulers.background import BackgroundScheduler

app = FastAPI(title="AEGIS News Intelligence Agent")
analyzer = SentimentIntensityAnalyzer()
RSS_FEEDS = [
    "https://feeds.bbci.co.uk/news/business/rss.xml", 
    "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml", 
    "https://feeds.finance.yahoo.com/rss/2.0/headline?s=^NDX&region=US&lang=en-US"
]
KEYWORDS = os.getenv("NEWS_KEYWORDS", "Tariff,Fed,War,Inflation,Recession,Nasdaq").split(",")
HEADERS = {"User-Agent": "ExaGuard-AEGIS-Scanner/1.0"}
latest_scan = {"risk_score": 0, "primary_driver": "None", "recommendation": "Pending", "verified_sources": [], "scan_timestamp": datetime.utcnow().isoformat()}

def perform_scan():
    global latest_scan
    articles = []
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url, request_headers=HEADERS)
            for entry in feed.entries[:10]:
                articles.append({
                    "headline": entry.get("title", ""), 
                    "summary": entry.get("summary", ""), 
                    "url": entry.get("link", ""), 
                    "publisher": feed.feed.get("title", "Unknown"), 
                    "published": entry.get("published", "")
                })
        except Exception as e: 
            print(f"Failed to parse {url}: {e}")

    scored_sources, total_score = [], 0
    matched_keywords_count = {k: 0 for k in KEYWORDS}
    for art in articles:
        text = f"{art['headline']} {art['summary']}".lower()
        matched = [k for k in KEYWORDS if k.lower() in text]
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
    
    if risk_score > 70 or avg_score < -0.5: 
        rec = "⚠️ HIGH RISK: Reduce Base Lot Size by 50%, Widen Grid Distance to 2x ATR, lower Max Floating Lots to 0.05."
    elif risk_score > 40 or avg_score < 0: 
        rec = "⚡ MODERATE RISK: Maintain Lot Size, but enable Dynamic ATR Grid Spacing."
    else: 
        rec = "🟢 FAVORABLE: Parameters optimal. Consider increasing Base Lot Size by 20%."

    latest_scan = {
        "scan_timestamp": datetime.utcnow().isoformat(), 
        "risk_score": risk_score, 
        "primary_driver": primary_driver, 
        "recommendation": rec, 
        "verified_sources": sorted(scored_sources, key=lambda x: x['individual_sentiment_score'])[:5]
    }
    print(f"Scan Complete. Risk Score: {risk_score}")

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
"""

with open('news-agent/scanner.py', 'w') as f:
    f.write(scanner_code)

print("✅ News Agent files created successfully!")
