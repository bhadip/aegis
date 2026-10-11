# ExaGuard AEGIS
**Autonomous Execution & Grid Intelligence System**

ExaGuard AEGIS is a sophisticated, news-driven algorithmic trading system designed for MetaTrader 5. It combines a disciplined basket-grid trading strategy with real-time geopolitical sentiment analysis to dynamically adjust risk parameters.

##  Key Features
- **Dynamic Basket Grid Strategy**: Places conditional Buy Limit orders based on equity-multiplied position sizing.
- **Real-Time News Intelligence**: Scrapes financial RSS feeds using VADER sentiment analysis to calculate a live Geopolitical Risk Score (0-100).
- **Adaptive Risk Management**: Automatically adjusts Take Profit targets (10/15/20 points) based on the current Risk Score.
- **Margin Level Circuit Breaker**: Automatically pauses new entries if Margin Level drops below 1000%.

## 📚 Documentation
- [Requirements](REQUIREMENTS.md)
- [System Design](DESIGN.md)
- [Installation Guide](INSTALLATION.md)
- [Operational Guide](OPERATIONAL_GUIDE.md)
