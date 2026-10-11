# System Design & Architecture
1. **News Agent**: Polls RSS feeds every 6 hours. VADER scores headlines against active keywords, generating a Risk Score.
2. **Bridge API**: Acts as the central nervous system, proxying requests between the Web UI, MT5 EA, and News Agent.
3. **MT5 EA**: Polls the Bridge API every 5 seconds via HTTP GET. Updates internal global variables and executes trading logic. Pushes live account status via HTTP POST.
4. **Trading Logic**: Places `Buy Limit` orders at `CurrentPrice - (GridDistance * Point)`. Max concurrent positions = `Floor(Equity / EquityMultiplier)`. Closes basket when average profit hits the dynamic TP.
