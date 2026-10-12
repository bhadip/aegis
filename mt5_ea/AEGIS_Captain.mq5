//+------------------------------------------------------------------+
//|                                      AEGIS_Captain.mq5           |
//+------------------------------------------------------------------+
#property copyright "ExaGuard AI"
#property version   "0.3.9"
#property strict

// LONG (SELL) POSITIONS ARE STRICTLY PROHIBITED. ONLY MARKET BUY IS ALLOWED.

#include <Trade/Trade.mqh>
CTrade trade;

input double InpBaseLotSize = 0.01;
input double InpGridDistance = 100.0;       // In PRICE POINTS (e.g., 100 = 100.00 price diff)
input double InpEquityMultiplier = 2500.0;
input double InpATHThresholdPct = 0.15;
input bool   InpUseH1RSIFilter = true;
input double InpMinH1RSI = 30.0;
input bool   InpEnableBasketClose = true;   // Toggle Basket Close feature

// TP Parameters (in price points)
input int    InpTPLowRisk = 20;             // TP when Risk Score < 40
input int    InpTPMedRisk = 15;             // TP when Risk Score 40-70
input int    InpTPHighRisk = 10;            // TP when Risk Score > 70

double CurrentLot = 0.01;
double CurrentGridDistance = 100.0;
double CurrentEquityMultiplier = 2500.0;
double CurrentATHThreshold = 0.15;
bool UseH1RSIFilter = true;
double MinH1RSI = 30.0;
bool EnableBasketClose = true;
int TPLowRisk = 20;
int TPMedRisk = 15;
int TPHighRisk = 10;
int CurrentRiskScore = 50;      
bool IsTradingPaused = false;   

int magicNumber = 88888;
string serverURL = "http://100.75.220.84:8000";
int lastMinute = -1;
int rsiHandles[5];
string tfNames[5] = {"M1", "M5", "M15", "M30", "H1"};
ENUM_TIMEFRAMES tfPeriods[5] = {PERIOD_M1, PERIOD_M5, PERIOD_M15, PERIOD_M30, PERIOD_H1};

int OnInit() {
   trade.SetExpertMagicNumber(magicNumber);
   CurrentLot = InpBaseLotSize;
   CurrentGridDistance = InpGridDistance;
   CurrentEquityMultiplier = InpEquityMultiplier;
   CurrentATHThreshold = InpATHThresholdPct;
   UseH1RSIFilter = InpUseH1RSIFilter;
   MinH1RSI = InpMinH1RSI;
   EnableBasketClose = InpEnableBasketClose;
   TPLowRisk = InpTPLowRisk;
   TPMedRisk = InpTPMedRisk;
   TPHighRisk = InpTPHighRisk;
   
   EventSetTimer(5);
   for(int i=0; i<5; i++) {
      rsiHandles[i] = iRSI(_Symbol, tfPeriods[i], 14, PRICE_CLOSE);
      if(rsiHandles[i] == INVALID_HANDLE) { Print("Failed to create RSI for ", tfNames[i]); return INIT_FAILED; }
   }
   Print("AEGIS Captain EA Initialized - Version 0.3.9");
   return INIT_SUCCEEDED;
}

void OnTimer() {
   char postData[]; char result[]; string headers;
   int resGet = WebRequest("GET", serverURL + "/api/v1/ea/config", headers, 2000, postData, result, headers);
   if(resGet == 200) ParseConfig(CharArrayToString(result));

   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double margin_level = AccountInfoDouble(ACCOUNT_MARGIN_LEVEL);
   int active_positions = PositionsTotal();
   if(margin_level == 0) margin_level = 99999;

   double high[], low[]; ArraySetAsSeries(high, true); ArraySetAsSeries(low, true);
   CopyHigh(_Symbol, PERIOD_H1, 0, 480, high); CopyLow(_Symbol, PERIOD_H1, 0, 480, low);
   double ath = high[ArrayMaximum(high)], atl = low[ArrayMinimum(low)];
   double pause_threshold = atl + ((ath - atl) * (1.0 - CurrentATHThreshold));
   bool trade_allowed = MQLInfoInteger(MQL_TRADE_ALLOWED);
   double currentPrice = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double h1Rsi = GetRSI(4);

   // DETERMINE EXACT REASON FOR NOT TRADING
   string restriction_reason = "None";
   if(IsTradingPaused) restriction_reason = "User Paused via Dashboard";
   else if(!trade_allowed) restriction_reason = "Algo Trading Disabled in MT5";
   else if(margin_level < 1000) restriction_reason = "Margin Level < 1000%";
   else if(UseH1RSIFilter && h1Rsi < MinH1RSI) restriction_reason = "H1 RSI < "+DoubleToString(MinH1RSI,1);
   else if(currentPrice > pause_threshold) restriction_reason = "Price in Top 15% of 4-Week Range";
   else {
      // Check internal filters
      int openCount = 0; double lowestPrice = DBL_MAX;
      for(int i = PositionsTotal() - 1; i >= 0; i--) {
         if(PositionGetSymbol(i) == _Symbol && PositionGetInteger(POSITION_MAGIC) == magicNumber) {
            double open = PositionGetDouble(POSITION_PRICE_OPEN);
            if(open < lowestPrice) lowestPrice = open;
            openCount++;
         }
      }
      
      if(openCount > 0) {
         double distance = MathAbs(currentPrice - lowestPrice);
         if(distance < CurrentGridDistance) {
            restriction_reason = "Waiting for Grid Distance (Current: "+DoubleToString(distance,1)+" pts)";
         } else {
            // Check RSI Hook
            string triggerTF = ""; 
            for(int i=0; i<4; i++) {
               double rsiCur=GetRSI(i); double rsiPrev=GetRSIPrev(i);
               if(rsiCur > rsiPrev && rsiCur < 40.0) { triggerTF=tfNames[i]; break; }
            }
            if(triggerTF == "") restriction_reason = "Waiting for RSI Hook (<40 & turning up)";
         }
      } else {
         // No positions open, check RSI Hook for initial entry
         string triggerTF = ""; 
         for(int i=0; i<4; i++) {
            double rsiCur=GetRSI(i); double rsiPrev=GetRSIPrev(i);
            if(rsiCur > rsiPrev && rsiCur < 40.0) { triggerTF=tfNames[i]; break; }
         }
         if(triggerTF == "") restriction_reason = "Waiting for Initial RSI Hook (<40 & turning up)";
      }
   }

   string statusUrl = serverURL + "/api/v1/ea/status?equity=" + DoubleToString(equity, 2) + 
                      "&balance=" + DoubleToString(balance, 2) + 
                      "&margin_level=" + DoubleToString(margin_level, 2) + 
                      "&active_positions=" + IntegerToString(active_positions) + 
                      "&ath=" + DoubleToString(ath, 2) + 
                      "&atl=" + DoubleToString(atl, 2) + 
                      "&threshold=" + DoubleToString(pause_threshold, 2) + 
                      "&trade_allowed=" + (trade_allowed ? "1" : "0") +
                      "&restriction_reason=" + restriction_reason;
   WebRequest("GET", statusUrl, headers, 2000, postData, result, headers);

   int currentMinute = (int)(TimeCurrent() / 60);
   if(currentMinute != lastMinute) { lastMinute = currentMinute; ExecuteBasketLogic(); }
}

void ExecuteBasketLogic() {
   if(IsTradingPaused) return;
   if(!MQLInfoInteger(MQL_TRADE_ALLOWED)) return;

   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   double ml = AccountInfoDouble(ACCOUNT_MARGIN_LEVEL); if(ml==0) ml=99999;
   if(ml < 1000) return;

   double h1Rsi = GetRSI(4);
   if(UseH1RSIFilter && h1Rsi < MinH1RSI) return;

   double high[], low[]; ArraySetAsSeries(high, true); ArraySetAsSeries(low, true);
   CopyHigh(_Symbol, PERIOD_H1, 0, 480, high); CopyLow(_Symbol, PERIOD_H1, 0, 480, low);
   double ath = high[ArrayMaximum(high)], atl = low[ArrayMinimum(low)];
   double pause_threshold = atl + ((ath - atl) * (1.0 - CurrentATHThreshold));
   double currentPrice = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   if(currentPrice > pause_threshold) return;

   int totalPositions = PositionsTotal();
   double lowestPrice = DBL_MAX; 
   int openCount = 0; 
   double totalFloatingPoints = 0;
   double current_lots = 0;

   for(int i = PositionsTotal() - 1; i >= 0; i--) {
      if(PositionGetSymbol(i) == _Symbol && PositionGetInteger(POSITION_MAGIC) == magicNumber) {
         double open = PositionGetDouble(POSITION_PRICE_OPEN);
         current_lots += PositionGetDouble(POSITION_VOLUME);
         if(open < lowestPrice) lowestPrice = open;
         totalFloatingPoints += (currentPrice - open);
         openCount++;
      }
   }

   double max_lots = (equity / CurrentEquityMultiplier) * 0.01;
   if(current_lots + CurrentLot > max_lots + 0.001) return;

   // BASKET CLOSE LOGIC
   if(EnableBasketClose && openCount > 0) {
      double baseTP = (CurrentRiskScore < 40) ? (double)TPLowRisk : ((CurrentRiskScore < 70) ? (double)TPMedRisk : (double)TPHighRisk);
      double targetTP = baseTP;
      if(h1Rsi >= 40.0 && h1Rsi <= 60.0) targetTP = baseTP * 0.5;
      
      double avgProfit = totalFloatingPoints / openCount;
      if(avgProfit >= targetTP) {
         Print("BASKET TP REACHED: Avg profit ", avgProfit, " pts >= Target ", targetTP, " pts. Closing all.");
         for(int i = PositionsTotal() - 1; i >= 0; i--) {
            if(PositionGetSymbol(i)==_Symbol && PositionGetInteger(POSITION_MAGIC)==magicNumber) {
               ulong t=PositionGetTicket(i); if(t>0) trade.PositionClose(t);
            }
         }
         return;
      }
   }

   // ENTRY LOGIC (MARKET BUY ONLY)
   if(totalPositions < 10) {
      string triggerTF = ""; double triggerRSI = 0;
      for(int i=0; i<4; i++) {
         double rsiCur=GetRSI(i); double rsiPrev=GetRSIPrev(i);
         if(rsiCur > rsiPrev && rsiCur < 40.0) { triggerTF=tfNames[i]; triggerRSI=rsiCur; break; }
      }

      if(triggerTF != "") {
         bool canEnter = true;
         if(openCount > 0) {
            for(int i=0; i<PositionsTotal(); i++) {
               if(PositionGetSymbol(i)==_Symbol && PositionGetInteger(POSITION_MAGIC)==magicNumber) {
                  double posPrice = PositionGetDouble(POSITION_PRICE_OPEN);
                  double distance = MathAbs(currentPrice - posPrice);
                  if(distance < CurrentGridDistance) { canEnter = false; break; }
               }
            }
         }
         
         if(canEnter) {
            double baseTP = (CurrentRiskScore < 40) ? (double)TPLowRisk : ((CurrentRiskScore < 70) ? (double)TPMedRisk : (double)TPHighRisk);
            double targetTP = baseTP;
            if(h1Rsi >= 40.0 && h1Rsi <= 60.0) targetTP = baseTP * 0.5;
            
            double tpPrice = NormalizeDouble(currentPrice + targetTP, _Digits);
            string comment = "AEGIS_MTF[" + triggerTF + "]_RSI[" + DoubleToString(triggerRSI,1) + "]_H1[" + DoubleToString(h1Rsi,1) + "]";
            
            if(trade.Buy(CurrentLot, _Symbol, 0, 0, tpPrice, comment)) {
               Print("✅ MARKET BUY: ", comment, " at ", currentPrice, " | Hard TP set at ", tpPrice, " (", targetTP, " price pts)");
            }
         }
      }
   }
}

double GetRSI(int tfIndex) { double buf[]; ArraySetAsSeries(buf, true); if(CopyBuffer(rsiHandles[tfIndex], 0, 0, 1, buf) > 0) return buf[0]; return 50.0; }
double GetRSIPrev(int tfIndex) { double buf[]; ArraySetAsSeries(buf, true); if(CopyBuffer(rsiHandles[tfIndex], 0, 1, 1, buf) > 0) return buf[0]; return 50.0; }

void ParseConfig(string data) {
   string pairs[]; string kv[]; ushort sep = StringGetCharacter("\n", 0); int total = StringSplit(data, sep, pairs);
   for(int i = 0; i < total; i++) {
      ushort eq = StringGetCharacter("=", 0);
      if(StringSplit(pairs[i], eq, kv) == 2) {
         if(kv[0] == "LOT") CurrentLot = StringToDouble(kv[1]);
         if(kv[0] == "GRID_DISTANCE") CurrentGridDistance = StringToDouble(kv[1]);
         if(kv[0] == "EQUITY_MULTIPLIER") CurrentEquityMultiplier = StringToDouble(kv[1]);
         if(kv[0] == "TP_LOW_RISK") TPLowRisk = (int)StringToInteger(kv[1]);
         if(kv[0] == "TP_MED_RISK") TPMedRisk = (int)StringToInteger(kv[1]);
         if(kv[0] == "TP_HIGH_RISK") TPHighRisk = (int)StringToInteger(kv[1]);
         if(kv[0] == "RISK_SCORE") CurrentRiskScore = (int)StringToInteger(kv[1]);
         if(kv[0] == "ENABLE_BASKET") EnableBasketClose = (kv[1] == "true");
         if(kv[0] == "IS_PAUSED") IsTradingPaused = (kv[1] == "true");
         if(kv[0] == "ATH_THRESHOLD") CurrentATHThreshold = StringToDouble(kv[1]);
      }
   }
}
//+------------------------------------------------------------------+
