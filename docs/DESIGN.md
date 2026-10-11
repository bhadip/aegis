# System Design & Architecture

## 1. Data Flow
1. **News Agent** polls configured RSS feeds. VADER scores headlines against active keywords, generating a Risk Score (0-100) and Bias.
2. **Web Dashboard** displays the Risk Score and allows the user to adjust EA parameters.
3. **Bridge API** stores these parameters in memory.
4. **MT5 EA** polls the Bridge API every 5 seconds via HTTP GET (`/api/v1/ea/config`).
5. **MT5 EA** updates its internal global variables and executes trading logic.
6. **MT5 EA** pushes live account status to the Bridge API via HTTP GET (`/api/v1/ea/status`).

## 2. Trading Logic (AEGIS_Captain v0.1)
- **Initial Entry**: Checks RSI(14) on M5. If RSI < 30, opens a **Market Buy** (0.01 lots).
- **Grid Entry**: Once the first position is open, places a **Buy Limit** exactly 10,000 points below the lowest open position. It will not place the next order until the price drops that far.
- **Position Sizing**: Max concurrent positions = `Floor(Equity / EquityMultiplier)`.
- **Basket Exit**: Calculates the average floating profit of all open positions. If `Average Profit >= Dynamic TP` (based on Risk Score), it closes the entire basket simultaneously.
  - Low Risk (<40): TP = 20 points
  - Medium Risk (40-70): TP = 15 points
  - High Risk (>70): TP = 10 points
- **Safety**: If `Margin Level < 1000%`, the EA halts all new order placements.

## 3. Security & Reliability
- Uses native MQL5 `WebRequest` (GET) for maximum compatibility with Wine/Docker environments.
- Internal Docker network isolates inter-service communication.
