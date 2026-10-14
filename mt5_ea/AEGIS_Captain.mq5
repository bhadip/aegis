//+------------------------------------------------------------------+
//|                                      AEGIS_Captain.mq5           |
//+------------------------------------------------------------------+
#property copyright "ExaGuard AI"
#property version   "0.4.0"
#property strict

// LONG (SELL) POSITIONS ARE STRICTLY PROHIBITED. ONLY MARKET BUY IS ALLOWED.

#include <Trade/Trade.mqh>
CTrade trade;

input double InpBaseLotSize = 0.01;
input double InpEquityMultiplier = 2500.0;
input double InpATHThresholdPct = 0.15;
input bool   InpUseH1RSIFilter = true;
input double InpMinH1RSI = 30.0;
input bool   InpEnableBasketClose = false;
// Dynamic grid: Grid = clamp(ATR_H1 * (0.60 + 0.80*R/100), GridMin, GridMax)
input bool   InpUseDynamicGrid = true;
input double InpGridDistance = 100.0;   // static fallback (price pts) if dynamic off or ATR invalid
input int    InpATRPeriod = 14;
input double InpGridMin = 50.0;
input double InpGridMax = 300.0;
// Tiered volatility TP: TP(t) = clamp(ATR_H1 * TierMult(t) * (1.40 - 0.80*R/100), TPMin, TPMax)
input double InpTPMin = 5.0;
input double InpTPMax = 100.0;

double CurrentLot = 0.01;
double CurrentEquityMultiplier = 2500.0;
double CurrentATHThreshold = 0.15;
bool UseH1RSIFilter = true;
double MinH1RSI = 30.0;
bool EnableBasketClose = false;
bool UseDynamicGrid = true;
double GridDistanceStatic = 100.0;
double GridMin = 50.0;
double GridMax = 300.0;
double TPMin = 5.0;
double TPMax = 100.0;
int CurrentRiskScore = 50;
bool IsTradingPaused = false;
double lastGridEff = 0.0;
double lastATR = 0.0;

int magicNumber = 88888;
string serverURL = "http://100.75.220.84:8000";
int lastMinute = -1;
int rsiHandles[5];
int atrHandle = INVALID_HANDLE;
string tfNames[5] = {"M1", "M5", "M15", "M30", "H1"};
ENUM_TIMEFRAMES tfPeriods[5] = {PERIOD_M1, PERIOD_M5, PERIOD_M15, PERIOD_M30, PERIOD_H1};

int OnInit() {
   trade.SetExpertMagicNumber(magicNumber);
   CurrentLot = InpBaseLotSize;
   CurrentEquityMultiplier = InpEquityMultiplier;
   CurrentATHThreshold = InpATHThresholdPct;
   UseH1RSIFilter = InpUseH1RSIFilter;
   MinH1RSI = InpMinH1RSI;
   EnableBasketClose = InpEnableBasketClose;
   UseDynamicGrid = InpUseDynamicGrid;
   GridDistanceStatic = InpGridDistance;
   GridMin = InpGridMin; GridMax = InpGridMax;
   TPMin = InpTPMin; TPMax = InpTPMax;
   EventSetTimer(5);
   for(int i=0; i<5; i++) {
      rsiHandles[i] = iRSI(_Symbol, tfPeriods[i], 14, PRICE_CLOSE);
      if(rsiHandles[i] == INVALID_HANDLE) { Print("Failed RSI handle ", tfNames[i]); return INIT_FAILED; }
   }
   atrHandle = iATR(_Symbol, PERIOD_H1, InpATRPeriod);
   if(atrHandle == INVALID_HANDLE) { Print("Failed ATR handle"); return INIT_FAILED; }
   Print("AEGIS Captain EA Initialized - Version 0.4.0 (dynamic grid + tiered TP)");
   return INIT_SUCCEEDED;
}

double ClampD(double v, double lo, double hi) { if(v < lo) return lo; if(v > hi) return hi; return v; }

double GetATR() {
   double buf[]; ArraySetAsSeries(buf, true);
   if(CopyBuffer(atrHandle, 0, 0, 1, buf) > 0) return buf[0];
   return 0.0;
}

double DynamicGrid() {
   double atr = GetATR();
   lastATR = atr;
   if(!UseDynamicGrid || atr <= 0.0) { lastGridEff = GridDistanceStatic; return GridDistanceStatic; }
   double mult = 0.60 + 0.80 * ((double)CurrentRiskScore / 100.0);
   double g = ClampD(atr * mult, GridMin, GridMax);
   lastGridEff = g;
   return g;
}

double TierMult(int tier) {
   if(tier <= 1) return 1.00;
   if(tier == 2) return 0.75;
   if(tier == 3) return 0.60;
   return 0.50;
}

double TierTP(int tier) {
   double atr = GetATR();
   if(atr <= 0.0) atr = 50.0; // documented fallback when ATR unavailable
   double g = 1.40 - 0.80 * ((double)CurrentRiskScore / 100.0);
   return ClampD(atr * TierMult(tier) * g, TPMin, TPMax);
}

double GetRSI(int tfIndex) { double buf[]; ArraySetAsSeries(buf, true); if(CopyBuffer(rsiHandles[tfIndex], 0, 0, 1, buf) > 0) return buf[0]; return 50.0; }
double GetRSIPrev(int tfIndex) { double buf[]; ArraySetAsSeries(buf, true); if(CopyBuffer(rsiHandles[tfIndex], 0, 1, 1, buf) > 0) return buf[0]; return 50.0; }

void OnTimer() {
   char postData[]; char result[]; string headers;
   int resGet = WebRequest("GET", serverURL + "/api/v1/ea/config", headers, 2000, postData, result, headers);
   if(resGet == 200) ParseConfig(CharArrayToString(result));

   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double margin_level = AccountInfoDouble(ACCOUNT_MARGIN_LEVEL);
   int active_positions = PositionsTotal();
   if(margin_level == 0) margin_level = 99999;

   double gridEff = DynamicGrid();

   double high[], low[]; ArraySetAsSeries(high, true); ArraySetAsSeries(low, true);
   CopyHigh(_Symbol, PERIOD_H1, 0, 480, high); CopyLow(_Symbol, PERIOD_H1, 0, 480, low);
   double ath = high[ArrayMaximum(high)], atl = low[ArrayMinimum(low)];
   double pause_threshold = atl + ((ath - atl) * (1.0 - CurrentATHThreshold));
   bool trade_allowed = MQLInfoInteger(MQL_TRADE_ALLOWED);
   double currentPrice = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double h1Rsi = GetRSI(4);

   string restriction_reason = "None";
   if(IsTradingPaused) restriction_reason = "User Paused via Dashboard";
   else if(!trade_allowed) restriction_reason = "Algo Trading Disabled in MT5";
   else if(margin_level < 1000) restriction_reason = "Margin Level < 1000%";
   else if(UseH1RSIFilter && h1Rsi < MinH1RSI) restriction_reason = "H1 RSI < " + DoubleToString(MinH1RSI,1);
   else if(currentPrice > pause_threshold) restriction_reason = "Price in Top 15% of 4-Week Range";
   else {
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
         if(distance < gridEff) restriction_reason = "Waiting for Grid Distance (Current: " + DoubleToString(distance,1) + " of " + DoubleToString(gridEff,1) + " pts)";
         else {
            string tf = "";
            for(int i=0; i<4; i++) { double rc=GetRSI(i); double rp=GetRSIPrev(i); if(rc > rp && rc < 40.0) { tf=tfNames[i]; break; } }
            if(tf == "") restriction_reason = "Waiting for RSI Hook (<40 & turning up)";
         }
      } else {
         string tf2 = "";
         for(int i=0; i<4; i++) { double rc=GetRSI(i); double rp=GetRSIPrev(i); if(rc > rp && rc < 40.0) { tf2=tfNames[i]; break; } }
         if(tf2 == "") restriction_reason = "Waiting for Initial RSI Hook (<40 & turning up)";
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
                      "&grid_eff=" + DoubleToString(gridEff, 1) +
                      "&atr=" + DoubleToString(lastATR, 1) +
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

   double gridEff = DynamicGrid();

   int openCount = 0;
   double current_lots = 0;
   double entries[16];
   for(int i = PositionsTotal() - 1; i >= 0; i--) {
      if(PositionGetSymbol(i) == _Symbol && PositionGetInteger(POSITION_MAGIC) == magicNumber) {
         current_lots += PositionGetDouble(POSITION_VOLUME);
         if(openCount < 16) { entries[openCount] = PositionGetDouble(POSITION_PRICE_OPEN); openCount++; }
      }
   }

   double max_lots = (equity / CurrentEquityMultiplier) * 0.01;
   if(current_lots + CurrentLot > max_lots + 0.001) return;

   // Tier ranking: highest entry price = tier 1 (insertion sort desc)
   for(int a=1; a<openCount; a++) { double v=entries[a]; int b=a-1; while(b>=0 && entries[b]<v) { entries[b+1]=entries[b]; b--; } entries[b+1]=v; }

   // Basket close (optional): avg floating pts >= avg of per-position tier TPs
   if(EnableBasketClose && openCount > 0) {
      double totalFloating = 0; double tpSum = 0;
      for(int t=0; t<openCount; t++) { totalFloating += (currentPrice - entries[t]); tpSum += TierTP(t+1); }
      double avgProfit = totalFloating / openCount;
      double avgTarget = tpSum / openCount;
      if(avgProfit >= avgTarget) {
         Print("BASKET TP: avg ", DoubleToString(avgProfit,1), " >= ", DoubleToString(avgTarget,1), ". Closing all.");
         for(int i = PositionsTotal() - 1; i >= 0; i--) {
            if(PositionGetSymbol(i)==_Symbol && PositionGetInteger(POSITION_MAGIC)==magicNumber) {
               ulong t=PositionGetTicket(i); if(t>0) trade.PositionClose(t);
            }
         }
         return;
      }
   }

   // Entry (MARKET BUY ONLY)
   if(openCount < 10) {
      string triggerTF = ""; double triggerRSI = 0;
      for(int i=0; i<4; i++) {
         double rsiCur=GetRSI(i); double rsiPrev=GetRSIPrev(i);
         if(rsiCur > rsiPrev && rsiCur < 40.0) { triggerTF=tfNames[i]; triggerRSI=rsiCur; break; }
      }
      if(triggerTF != "") {
         bool canEnter = true;
         for(int i=0; i<openCount; i++) {
            if(MathAbs(currentPrice - entries[i]) < gridEff) { canEnter = false; break; }
         }
         if(canEnter) {
            int tier = openCount + 1;
            double targetTP = TierTP(tier);
            double tpPrice = NormalizeDouble(currentPrice + targetTP, _Digits);
            string comment = "AEGIS_T" + IntegerToString(tier) + "_MTF[" + triggerTF + "]_RSI[" + DoubleToString(triggerRSI,1) + "]";
            Print("TP MATH: tier=", tier, " atr=", DoubleToString(lastATR,1), " risk=", CurrentRiskScore, " target=", DoubleToString(targetTP,1), " tpPrice=", tpPrice, " gridEff=", DoubleToString(gridEff,1));
            if(trade.Buy(CurrentLot, _Symbol, 0, 0, tpPrice, comment)) {
               Print("MARKET BUY tier ", tier, " at ", currentPrice, " | TP ", tpPrice);
            }
         }
      }
   }
}

void ParseConfig(string data) {
   string pairs[]; string kv[]; ushort sep = StringGetCharacter("\n", 0); int total = StringSplit(data, sep, pairs);
   for(int i = 0; i < total; i++) {
      ushort eq = StringGetCharacter("=", 0);
      if(StringSplit(pairs[i], eq, kv) == 2) {
         if(kv[0] == "LOT") CurrentLot = StringToDouble(kv[1]);
         if(kv[0] == "GRID_DISTANCE") GridDistanceStatic = StringToDouble(kv[1]);
         if(kv[0] == "EQUITY_MULTIPLIER") CurrentEquityMultiplier = StringToDouble(kv[1]);
         if(kv[0] == "RISK_SCORE") CurrentRiskScore = (int)StringToInteger(kv[1]);
         if(kv[0] == "ENABLE_BASKET") EnableBasketClose = (kv[1] == "true");
         if(kv[0] == "IS_PAUSED") IsTradingPaused = (kv[1] == "true");
         if(kv[0] == "ATH_THRESHOLD") CurrentATHThreshold = StringToDouble(kv[1]);
      }
   }
}
//+------------------------------------------------------------------+
