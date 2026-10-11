# Operational Guide

## Daily Operations
1. **Morning Check**: Open the Dashboard. Verify Account Status shows "Very Safe" or "Safe" (Margin Level > 1000%).
2. **News Scan**: Navigate to the **News Intelligence** tab and click **Scan Now**. Review the Risk Score.
3. **Parameter Adjustment**: 
   - If Risk Score is **High (>70)**: Ensure "TP High Risk" is set to 10 points to scalp quick bounces.
   - If Risk Score is **Low (<40)**: You may increase "TP Low Risk" to 20 points to maximize mean-reversion profits.
4. **Equity Management**: If Margin Level approaches 1000%, manually top up the MT5 account equity. The EA will automatically resume trading once ML > 1000%.

## Understanding the EA Behavior
- **Why isn't it opening a trade?** The EA is waiting for the RSI(14) on the M5 chart to drop below 30. It will not blindly place orders.
- **Why is the Grid Distance so large (10,000)?** This equals a 100.00 price difference on the Nasdaq 100. This prevents the EA from over-leveraging during minor fluctuations and ensures it only averages down during significant, structural pullbacks.

## Troubleshooting
- **Dashboard shows "Disconnected"**: Ensure the EA is attached to the chart and the WebRequest URL (`http://<YOUR_HOST_IP>:8000`) is allowed in MT5 Options.
- **EA not placing orders**: Check if Margin Level is below 1000% (triggers Safety Pause) or if RSI is currently above 30.
