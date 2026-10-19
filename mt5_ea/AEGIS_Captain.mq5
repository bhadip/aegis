//+------------------------------------------------------------------+
//|                                      AEGIS_Captain.mq5           |
//+------------------------------------------------------------------+
#property copyright "ExaGuard AI"
#property version   "0.11.0"
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
input bool   InpUseDynamicGrid = true;
input double InpGridDistance = 100.0;   // static fallback (price pts)
input int    InpATRPeriod = 14;
// Gradual grid coefficients (also adjustable from Dashboard Settings)
input double InpGridMin = 50.0;         // floor for grid base G
input double InpGridMax = 300.0;        // cap for grid base G
input double InpGridStepPct = 25.0;     // extra % per tier: gap(k) = G * (1 + step/100*(k-1))
// Tiered TP coefficients (also adjustable from Dashboard Settings)
input double InpTPMin = 10.0;           // TP floor (price pts)
input double InpTPMax = 100.0;          // TP cap (price pts)
input double InpTPMult1 = 0.60;         // tier-1 multiplier (smallest, fastest exit)
input double InpTPStep = 0.20;          // multiplier added per tier
input double InpTPMultMax = 1.40;       // multiplier cap (deepest tier)

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
double GridStepPct = 25.0;
double TPMin = 10.0;
double TPMax = 100.0;
double TPMult1 = 0.60;
double TPStep = 0.20;
double TPMultMax = 1.40;
int CurrentRiskScore = 50;
bool IsTradingPaused = false;
double lastGridEff = 0.0;
double lastATR = 0.0;
string exportRequestId = "0";
string lastAction = "";
ulong prevTickets[32];
int prevCount = 0;
string lastExportId = "0";
int exportDays = 30;
string exportPrice = "BID";
string lastScanId = "0";
string scanLogId = "0";
string scanBias = "";
int scanArticles = 0;
double scanAvgSent = 0;

int magicNumber = 88888;
string serverURL = "http://100.75.220.84:9191";
int lastMinute = -1;
int rsiHandles[6];
int atrHandles[6];
int atrH1Handle = INVALID_HANDLE;
string tfNames[6] = {"M1", "M5", "M15", "M30", "H1", "D1"};
ENUM_TIMEFRAMES tfPeriods[6] = {PERIOD_M1, PERIOD_M5, PERIOD_M15, PERIOD_M30, PERIOD_H1, PERIOD_D1};

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
   GridMin = InpGridMin; GridMax = InpGridMax; GridStepPct = InpGridStepPct;
   TPMin = InpTPMin; TPMax = InpTPMax;
   TPMult1 = InpTPMult1; TPStep = InpTPStep; TPMultMax = InpTPMultMax;
   EventSetTimer(5);
   for(int i=0; i<6; i++) {
      rsiHandles[i] = iRSI(_Symbol, tfPeriods[i], 14, PRICE_CLOSE);
      atrHandles[i] = iATR(_Symbol, tfPeriods[i], 14);
      if(rsiHandles[i] == INVALID_HANDLE || atrHandles[i] == INVALID_HANDLE) { Print("Failed handle ", tfNames[i]); return INIT_FAILED; }
   }
   atrH1Handle = atrHandles[4];
   Print("AEGIS Captain EA Initialized - Version 0.11.0");
   return INIT_SUCCEEDED;
}

double ClampD(double v, double lo, double hi) { if(v < lo) return lo; if(v > hi) return hi; return v; }
double GetATR() { double buf[]; ArraySetAsSeries(buf, true); if(CopyBuffer(atrH1Handle, 0, 0, 1, buf) > 0) return buf[0]; return 0.0; }
double GetRSI(int tfIndex) { double buf[]; ArraySetAsSeries(buf, true); if(CopyBuffer(rsiHandles[tfIndex], 0, 0, 1, buf) > 0) return buf[0]; return 50.0; }
double GetRSIPrev(int tfIndex) { double buf[]; ArraySetAsSeries(buf, true); if(CopyBuffer(rsiHandles[tfIndex], 0, 1, 1, buf) > 0) return buf[0]; return 50.0; }

double DynamicGrid() {
   double atr = GetATR();
   lastATR = atr;
   if(!UseDynamicGrid || atr <= 0.0) { lastGridEff = GridDistanceStatic; return GridDistanceStatic; }
   double mult = 0.60 + 0.80 * ((double)CurrentRiskScore / 100.0);
   lastGridEff = ClampD(atr * mult, GridMin, GridMax);
   return lastGridEff;
}

double TierMult(int tier) {
   double m = TPMult1 + TPStep * (double)(tier - 1);
   if(m > TPMultMax) m = TPMultMax;
   return m;
}

double TierTP(int tier) {
   double atr = GetATR();
   if(atr <= 0.0) atr = 50.0;
   double g = 1.40 - 0.80 * ((double)CurrentRiskScore / 100.0);
   return ClampD(atr * TierMult(tier) * g, TPMin, TPMax);
}

double NextGap(int openCount, double g) {
   if(openCount <= 0) return 0.0;
   return g * (1.0 + (GridStepPct / 100.0) * (double)(openCount - 1));
}

int SendChunk(string body) {
   char data[]; char res[]; string rh;
   StringToCharArray(body, data, 0, StringLen(body), CP_UTF8);
   string headers = "Content-Type: text/csv\r\n";
   return WebRequest("POST", serverURL + "/api/v1/tools/export_chunk", headers, 15000, data, res, rh);
}

void DoExport() {
   datetime cutoff = TimeCurrent() - exportDays * 86400;
   double askOff = 0.0;
   if(exportPrice == "ASK") {
      askOff = (double)SymbolInfoInteger(_Symbol, SYMBOL_SPREAD) * _Point;
      if(askOff <= 0.0) askOff = SymbolInfoDouble(_Symbol, SYMBOL_ASK) - SymbolInfoDouble(_Symbol, SYMBOL_BID);
   }
   Print("EXPORT basis=", exportPrice, " askOff=", DoubleToString(askOff, _Digits));
   string chunk = "time,timeframe,basis,open,high,low,close,tick_volume,rsi14,atr14\n";
   int rows = 0; int totalRows = 0;
   for(int t=0; t<6; t++) {
      int bars = iBars(_Symbol, tfPeriods[t]);
      if(bars <= 0) continue;
      MqlRates rates[]; ArraySetAsSeries(rates, true);
      double rsiBuf[]; double atrBuf[]; ArraySetAsSeries(rsiBuf, true); ArraySetAsSeries(atrBuf, true);
      if(CopyRates(_Symbol, tfPeriods[t], 0, bars, rates) <= 0) continue;
      CopyBuffer(rsiHandles[t], 0, 0, bars, rsiBuf);
      CopyBuffer(atrHandles[t], 0, 0, bars, atrBuf);
      for(int i = bars - 1; i >= 0; i--) {
         if(rates[i].time < cutoff) continue;
         chunk += TimeToString(rates[i].time, TIME_DATE|TIME_MINUTES) + "," + tfNames[t] + "," + exportPrice + "," +
                  DoubleToString(rates[i].open + askOff, _Digits) + "," + DoubleToString(rates[i].high + askOff, _Digits) + "," +
                  DoubleToString(rates[i].low + askOff, _Digits) + "," + DoubleToString(rates[i].close + askOff, _Digits) + "," +
                  IntegerToString((long)rates[i].tick_volume) + "," +
                  DoubleToString(rsiBuf[i], 2) + "," + DoubleToString(atrBuf[i], 2) + "\n";
         rows++; totalRows++;
         if(rows >= 300) { SendChunk(chunk); chunk = ""; rows = 0; }
      }
   }
   if(chunk != "") SendChunk(chunk);
   char d[]; char r2[]; string h2 = ""; string rh2;
   WebRequest("GET", serverURL + "/api/v1/tools/export_done?id=" + lastExportId, h2, 10000, d, r2, rh2);
   Print("EXPORT COMPLETE: ", totalRows, " rows over ", exportDays, " days, 6 timeframes.");
}

void LogScore() {
   int h = FileOpen("score_log.csv", FILE_CSV|FILE_READ|FILE_WRITE, ',');
   if(h == INVALID_HANDLE) { Print("score_log.csv open failed"); return; }
   if(FileSize(h) == 0) FileWrite(h, "timestamp", "scan_id", "risk_score", "bias", "articles", "avg_sent_pct", "bid", "h1_atr");
   FileSeek(h, 0, SEEK_END);
   FileWrite(h, TimeToString(TimeCurrent(), TIME_DATE|TIME_SECONDS), lastScanId, IntegerToString(CurrentRiskScore), scanBias,
             IntegerToString(scanArticles), DoubleToString(scanAvgSent, 0),
             DoubleToString(SymbolInfoDouble(_Symbol, SYMBOL_BID), _Digits), DoubleToString(GetATR(), 1));
   FileClose(h);
   Print("SCORE LOGGED: ", CurrentRiskScore, " ", scanBias, " n=", scanArticles);
}

void OnTimer() {
   char postData[]; char result[]; string headers;
   int resGet = WebRequest("GET", serverURL + "/api/v1/ea/config", headers, 2000, postData, result, headers);
   if(resGet == 200) ParseConfig(CharArrayToString(result));

   if(lastScanId != "0" && scanLogId != lastScanId) { scanLogId = lastScanId; LogScore(); }

   if(exportRequestId != "0" && exportRequestId != lastExportId) {
      lastExportId = exportRequestId;
      DoExport();
   }

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
   datetime athT = iTime(_Symbol, PERIOD_H1, ArrayMaximum(high));
   datetime atlT = iTime(_Symbol, PERIOD_H1, ArrayMinimum(low));

   int openCount = 0; double lowestPrice = DBL_MAX; double curLots = 0;
   ulong curTickets[32]; int curCount = 0; double rawEntries[16]; double rawTps[16];
   for(int i = PositionsTotal() - 1; i >= 0; i--) {
      if(PositionGetSymbol(i) == _Symbol && PositionGetInteger(POSITION_MAGIC) == magicNumber) {
         double open = PositionGetDouble(POSITION_PRICE_OPEN);
         if(open < lowestPrice) lowestPrice = open;
         curLots += PositionGetDouble(POSITION_VOLUME);
         if(openCount < 16) { rawEntries[openCount] = open; rawTps[openCount] = PositionGetDouble(POSITION_TP); }
         openCount++;
         if(curCount < 32) { curTickets[curCount] = (ulong)PositionGetInteger(POSITION_TICKET); curCount++; }
      }
   }
   // detect externally closed positions (TP hits) for Last Action line
   for(int pi = 0; pi < prevCount; pi++) {
      bool found = false;
      for(int ci = 0; ci < curCount; ci++) if(curTickets[ci] == prevTickets[pi]) { found = true; break; }
      if(!found) {
         HistorySelect(TimeCurrent() - 604800, TimeCurrent() + 60);
         for(int d = HistoryDealsTotal() - 1; d >= 0; d--) {
            ulong dt = HistoryDealGetTicket(d);
            if(dt > 0 && (ulong)HistoryDealGetInteger(dt, DEAL_POSITION_ID) == prevTickets[pi] &&
               (ENUM_DEAL_ENTRY)HistoryDealGetInteger(dt, DEAL_ENTRY) == DEAL_ENTRY_OUT) {
               double pl = HistoryDealGetDouble(dt, DEAL_PROFIT) + HistoryDealGetDouble(dt, DEAL_SWAP) + HistoryDealGetDouble(dt, DEAL_COMMISSION);
               ENUM_DEAL_REASON rs = (ENUM_DEAL_REASON)HistoryDealGetInteger(dt, DEAL_REASON);
               string rstr = (rs == DEAL_REASON_TP) ? "TP" : ((rs == DEAL_REASON_CLIENT) ? "EA/manual" : "other");
               lastAction = TimeToString(TimeCurrent(), TIME_DATE|TIME_MINUTES) + "_CLOSED_#" + IntegerToString((long)prevTickets[pi]) + "_" + rstr + "_P/L_" + DoubleToString(pl, 2);
               break;
            }
         }
      }
   }
   prevCount = curCount;
   for(int ci2 = 0; ci2 < curCount; ci2++) prevTickets[ci2] = curTickets[ci2];
   // tier-ordered entries (desc) and pos payload
   for(int a2=1; a2<openCount; a2++) { double v=rawEntries[a2]; double vt=rawTps[a2]; int b2=a2-1; while(b2>=0 && rawEntries[b2]<v) { rawEntries[b2+1]=rawEntries[b2]; rawTps[b2+1]=rawTps[b2]; b2--; } rawEntries[b2+1]=v; rawTps[b2+1]=vt; }
   string posPayload = "";
   for(int t2=0; t2<openCount; t2++) { if(t2>0) posPayload += ","; posPayload += DoubleToString(rawEntries[t2],2) + "|" + DoubleToString(rawTps[t2],2); }

   string hookStr = "";
   for(int hi=0; hi<4; hi++) { double hrc=GetRSI(hi); double hrp=GetRSIPrev(hi); if(hrc > hrp && hrc < 40.0) { hookStr = tfNames[hi] + "_" + DoubleToString(hrc,1); break; } }
   string restriction_reason = "None";
   if(IsTradingPaused) restriction_reason = "User Paused via Dashboard";
   else if(!trade_allowed) restriction_reason = "Algo Trading Disabled in MT5";
   else if(margin_level < 1000) restriction_reason = "Margin Level < 1000%";
   else if(UseH1RSIFilter && h1Rsi < MinH1RSI) restriction_reason = "H1 RSI < " + DoubleToString(MinH1RSI,1);
   else if(currentPrice > pause_threshold) restriction_reason = "Price in Top 15% of 4-Week Range";
   else if(curLots + CurrentLot > (equity / CurrentEquityMultiplier) * 0.01 + 0.0009) restriction_reason = "Exposure cap reached (" + DoubleToString(curLots,2) + " + " + DoubleToString(CurrentLot,2) + " > " + DoubleToString((equity / CurrentEquityMultiplier) * 0.01,2) + " lots)";
   else if(openCount > 0) {
      double need = NextGap(openCount, gridEff);
      double dist = lowestPrice - currentPrice;
      if(dist < need) restriction_reason = "Waiting for Grid Distance (Current: " + DoubleToString(dist,1) + " of " + DoubleToString(need,1) + " pts to next tier)";
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
                      "&ath_t=" + IntegerToString((long)athT) +
                      "&atl_t=" + IntegerToString((long)atlT) +
                      "&restriction_reason=" + restriction_reason +
                      "&g_h1=" + DoubleToString(h1Rsi,1) +
                      "&g_h1min=" + DoubleToString(MinH1RSI,1) +
                      "&g_athpct=" + DoubleToString((ath>atl)?(currentPrice-atl)/(ath-atl)*100.0:0.0,1) +
                      "&g_lots=" + DoubleToString(curLots,2) +
                      "&g_lotmax=" + DoubleToString((equity / CurrentEquityMultiplier) * 0.01,2) +
                      "&g_dist=" + DoubleToString(lowestPrice - currentPrice,1) +
                      "&g_need=" + DoubleToString(NextGap(openCount, gridEff),1) +
                      "&g_hook=" + hookStr +
                      "&g_cur=" + DoubleToString(currentPrice,2) +
                      "&pos=" + posPayload +
                      "&last_action=" + lastAction;
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

   int openCount = 0; double current_lots = 0; double entries[16];
   for(int i = PositionsTotal() - 1; i >= 0; i--) {
      if(PositionGetSymbol(i) == _Symbol && PositionGetInteger(POSITION_MAGIC) == magicNumber) {
         current_lots += PositionGetDouble(POSITION_VOLUME);
         if(openCount < 16) { entries[openCount] = PositionGetDouble(POSITION_PRICE_OPEN); openCount++; }
      }
   }

   double max_lots = (equity / CurrentEquityMultiplier) * 0.01;
   if(current_lots + CurrentLot > max_lots + 0.001) return;

   for(int a=1; a<openCount; a++) { double v=entries[a]; int b=a-1; while(b>=0 && entries[b]<v) { entries[b+1]=entries[b]; b--; } entries[b+1]=v; }
   double lowestPrice = (openCount > 0) ? entries[openCount-1] : DBL_MAX;

   if(EnableBasketClose && openCount > 0) {
      double totalFloating = 0; double tpSum = 0;
      for(int t=0; t<openCount; t++) { totalFloating += (currentPrice - entries[t]); tpSum += TierTP(t+1); }
      if(totalFloating / openCount >= tpSum / openCount) {
         Print("BASKET TP reached. Closing all.");
         lastAction = TimeToString(TimeCurrent(), TIME_DATE|TIME_MINUTES) + "_BASKET_CLOSE_avg_" + DoubleToString(totalFloating / openCount,1) + "pts";
         for(int i = PositionsTotal() - 1; i >= 0; i--) {
            if(PositionGetSymbol(i)==_Symbol && PositionGetInteger(POSITION_MAGIC)==magicNumber) {
               ulong t=PositionGetTicket(i); if(t>0) trade.PositionClose(t);
            }
         }
         return;
      }
   }

   if(openCount < 10) {
      string triggerTF = ""; double triggerRSI = 0;
      for(int i=0; i<4; i++) {
         double rsiCur=GetRSI(i); double rsiPrev=GetRSIPrev(i);
         if(rsiCur > rsiPrev && rsiCur < 40.0) { triggerTF=tfNames[i]; triggerRSI=rsiCur; break; }
      }
      if(triggerTF != "") {
         bool canEnter = true;
         if(openCount > 0) {
            double need = NextGap(openCount, gridEff);
            if((lowestPrice - currentPrice) < need) canEnter = false;
         }
         if(canEnter) {
            int tier = openCount + 1;
            double targetTP = TierTP(tier);
            double tpPrice = NormalizeDouble(currentPrice + targetTP, _Digits);
            string comment = "AEGIS_T" + IntegerToString(tier) + "_MTF[" + triggerTF + "]_RSI[" + DoubleToString(triggerRSI,1) + "]";
            Print("TP MATH: tier=", tier, " atr=", DoubleToString(lastATR,1), " risk=", CurrentRiskScore, " target=", DoubleToString(targetTP,1), " tpPrice=", tpPrice, " gridEff=", DoubleToString(gridEff,1), " nextGap=", DoubleToString(NextGap(openCount, gridEff),1));
            if(trade.Buy(CurrentLot, _Symbol, 0, 0, tpPrice, comment)) {
               Print("MARKET BUY tier ", tier, " at ", currentPrice, " | TP ", tpPrice);
               lastAction = TimeToString(TimeCurrent(), TIME_DATE|TIME_MINUTES) + "_BUY_" + DoubleToString(CurrentLot,2) + "_@" + DoubleToString(currentPrice,2) + "_T" + IntegerToString(tier) + "_TP_" + DoubleToString(tpPrice,2);
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
         if(kv[0] == "EXPORT_REQUEST") exportRequestId = kv[1];
         if(kv[0] == "EXPORT_DAYS") exportDays = (int)StringToInteger(kv[1]);
         if(kv[0] == "EXPORT_PRICE") exportPrice = kv[1];
         if(kv[0] == "SCAN_ID") lastScanId = kv[1];
         if(kv[0] == "SCAN_BIAS") scanBias = kv[1];
         if(kv[0] == "SCAN_ARTICLES") scanArticles = (int)StringToInteger(kv[1]);
         if(kv[0] == "SCAN_AVG_SENT") scanAvgSent = StringToDouble(kv[1]);
         if(kv[0] == "GRID_MIN") GridMin = StringToDouble(kv[1]);
         if(kv[0] == "GRID_MAX") GridMax = StringToDouble(kv[1]);
         if(kv[0] == "GRID_STEP_PCT") GridStepPct = StringToDouble(kv[1]);
         if(kv[0] == "TP_MIN") TPMin = StringToDouble(kv[1]);
         if(kv[0] == "TP_MAX") TPMax = StringToDouble(kv[1]);
         if(kv[0] == "TP_T1_MULT") TPMult1 = StringToDouble(kv[1]);
         if(kv[0] == "TP_TIER_STEP") TPStep = StringToDouble(kv[1]);
         if(kv[0] == "TP_TIER_MAX") TPMultMax = StringToDouble(kv[1]);
      }
   }
}
//+------------------------------------------------------------------+
