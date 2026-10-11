# ExaGuard AEGIS
**Autonomous Execution & Grid Intelligence System**

ExaGuard AEGIS is a sophisticated, news-driven algorithmic trading system designed for MetaTrader 5. It combines a disciplined, RSI-triggered basket-grid strategy with real-time geopolitical sentiment analysis to dynamically adjust risk parameters.

## 🌟 Key Features
- **Signal-Triggered Initial Entry**: Places an initial Market Buy order *only* when RSI(14) on the M5 timeframe drops below 30 (Oversold).
- **Wide-Spacing Grid Averaging**: Subsequent Buy Limit orders are placed exactly 10,000 points (100.00 price difference) below the lowest open position to safely average down during deep pullbacks.
- **Real-Time News Intelligence**: Scrapes financial RSS feeds using VADER sentiment analysis to calculate a live Geopolitical Risk Score (0-100).
- **Adaptive Basket Take Profit**: Automatically adjusts the basket exit target (10/15/20 points) based on the current Risk Score (Bearish/Neutral/Bullish).
- **Equity-Based Position Sizing**: Strictly limits exposure to 0.01 lots per $2,500 of equity.
- **Margin Level Circuit Breaker**: Automatically pauses new entries if Margin Level drops below 1000%.

## 🏗️ Architecture
- **MT5 EA (`AEGIS_Captain.mq5`)**: Executes trades, manages the grid, and polls the Bridge API every 5 seconds for config updates.
- **Bridge API (Python/FastAPI)**: Central nervous system proxying requests between the Web UI, MT5 EA, and News Agent.
- **News Agent (Python/FastAPI)**: Independently scrapes RSS feeds, performs sentiment analysis, and exposes configuration endpoints.
- **Web UI (Vue.js + Tailwind CSS)**: Responsive, real-time dashboard for monitoring and control.

## 📚 Documentation
- [Requirements](REQUIREMENTS.md)
- [System Design](DESIGN.md)
- [Installation Guide](INSTALLATION.md)
- [Operational Guide](OPERATIONAL_GUIDE.md)
