//+------------------------------------------------------------------+
//|                                      AEGIS_Captain.mq5           |
//+------------------------------------------------------------------+
#property copyright "ExaGuard AI"
#property version   "0.1"
#property strict

#include <Trade/Trade.mqh>
CTrade trade;

input double InpBaseLotSize = 0.01;
input int    InpGridDistance = 10000;
input double InpEquityMultiplier = 2500;

double CurrentLot = 0.01;
int CurrentGridDistance = 10000;
double CurrentEquityMultiplier = 2500;
int TPLowRisk = 20;
int TPMedRisk = 15;
int TPHighRisk = 10;
int CurrentRiskScore = 50;

int magicNumber = 88888;
string serverURL = "http://100.75.220.84:8000";
int lastMinute = -1;
int rsiHandle;

int OnInit() {
   trade.SetExpertMagicNumber(magicNumber);
   CurrentLot = InpBaseLotSize;
   CurrentGridDistance = InpGridDistance;
   CurrentEquityMultiplier = InpEquityMultiplier;
   EventSetTimer(5);
   
   rsiHandle = iRSI(_Symbol, PERIOD_M5, 14, PRICE_CLOSE);
   if(rsiHandle == INVALID_HANDLE) {
      Print("Failed to create RSI indicator");
      return INIT_FAILED;
   }
   
   Print("AEGIS Captain EA Initialized - Version 0.1");
   return INIT_SUCCEEDED;
}

void OnTimer() {
   char postData[];
   char result[];
   string headers;
   
   int resGet = WebRequest("GET", serverURL + "/api/v1/ea/config", headers, 2000, postData, result, headers);
   if(resGet == 200) {
      string response = CharArrayToString(result);
      ParseConfig(response);
   }

   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double margin_level = AccountInfoDouble(ACCOUNT_MARGIN_LEVEL);
   int active_positions = PositionsTotal();
   
   if(margin_level == 0) margin_level = 99999;

   string statusUrl = serverURL + "/api/v1/ea/status?equity=" + DoubleToString(equity, 2) + 
                      "&balance=" + DoubleToString(balance, 2) + 
                      "&margin_level=" + DoubleToString(margin_level, 2) + 
                      "&active_positions=" + IntegerToString(active_positions);
   
   int resPost = WebRequest("GET", statusUrl, headers, 2000, postData, result, headers);
   
   int currentMinute = (int)(TimeCurrent() / 60);
   if(currentMinute != lastMinute) {
      lastMinute = currentMinute;
      ExecuteBasketLogic();
   }
}

void ExecuteBasketLogic() {
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   double ml = AccountInfoDouble(ACCOUNT_MARGIN_LEVEL);
   if(ml == 0) ml = 99999;
   
   // Count both open positions and pending orders to prevent over-exposure
   int totalExposure = PositionsTotal() + OrdersTotal();
   int maxPositions = (int)MathFloor(equity / CurrentEquityMultiplier);
   
   if(ml < 1000) {
      Print("SAFETY PAUSE: ML% is ", ml, "% (below 1000%)");
      return;
   }

   double lowestPrice = DBL_MAX;
   int openCount = 0;
   double totalFloatingPoints = 0;

   for(int i = PositionsTotal() - 1; i >= 0; i--) {
      if(PositionGetSymbol(i) == _Symbol && PositionGetInteger(POSITION_MAGIC) == magicNumber) {
         double open = PositionGetDouble(POSITION_PRICE_OPEN);
         double current = SymbolInfoDouble(_Symbol, SYMBOL_BID);
         if(open < lowestPrice) lowestPrice = open;
         totalFloatingPoints += (current - open) / _Point;
         openCount++;
      }
   }

   // BASKET EXIT LOGIC
   int targetTP = (CurrentRiskScore < 40) ? TPLowRisk : ((CurrentRiskScore < 70) ? TPMedRisk : TPHighRisk);
   if(openCount > 0 && (totalFloatingPoints / openCount) >= targetTP) {
      Print("BASKET TP REACHED: Closing all positions");
      for(int i = PositionsTotal() - 1; i >= 0; i--) {
         if(PositionGetSymbol(i) == _Symbol && PositionGetInteger(POSITION_MAGIC) == magicNumber) {
            ulong ticket = PositionGetTicket(i);
            if(ticket > 0) trade.PositionClose(ticket);
         }
      }
      return;
   }

   // ENTRY LOGIC
   if(totalExposure < maxPositions) {
      
      if(PositionsTotal() == 0) {
         // RULE 1: INITIAL ENTRY - Market Buy when RSI < 30
         double rsiBuffer[];
         ArraySetAsSeries(rsiBuffer, true);
         if(CopyBuffer(rsiHandle, 0, 0, 1, rsiBuffer) > 0) {
            if(rsiBuffer[0] < 30.0) {
               if(trade.Buy(CurrentLot, _Symbol, 0, 0, 0, "AEGIS Initial RSI Entry")) {
                  Print("Opened Initial Buy at Market. RSI: ", rsiBuffer[0]);
               }
            }
         }
      } else {
         // RULE 2: GRID ENTRY - Buy Limit 10,000 points below lowest open position
         double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         double stopLevel = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * _Point;
         if(stopLevel == 0) stopLevel = 10 * _Point;
         
         double nextGridPrice = lowestPrice - (CurrentGridDistance * _Point);
         
         // Ensure the limit price is valid (below current ASK - stop level)
         if(nextGridPrice < ask - stopLevel) {
            bool exists = false;
            int ordersTotal = OrdersTotal();
            for(int i = 0; i < ordersTotal; i++) {
               ulong ticket = OrderGetTicket(i);
               if(ticket > 0) {
                  string orderSymbol = OrderGetString(ORDER_SYMBOL);
                  if(orderSymbol == _Symbol && MathAbs(OrderGetDouble(ORDER_PRICE_OPEN) - nextGridPrice) < _Point) {
                     exists = true;
                     break;
                  }
               }
            }
            
            if(!exists) {
               if(trade.BuyLimit(CurrentLot, nextGridPrice, _Symbol, 0, 0, ORDER_TIME_GTC, 0, "AEGIS Grid")) {
                  Print("Placed Grid Buy Limit at ", nextGridPrice);
               }
            }
         }
      }
   }
}

void ParseConfig(string data) {
   string pairs[];
   string kv[];
   ushort sep = StringGetCharacter("\n", 0);
   int total = StringSplit(data, sep, pairs);
   
   for(int i = 0; i < total; i++) {
      ushort eq = StringGetCharacter("=", 0);
      if(StringSplit(pairs[i], eq, kv) == 2) {
         if(kv[0] == "LOT") CurrentLot = StringToDouble(kv[1]);
         if(kv[0] == "GRID_DISTANCE") CurrentGridDistance = (int)StringToInteger(kv[1]);
         if(kv[0] == "EQUITY_MULTIPLIER") CurrentEquityMultiplier = StringToDouble(kv[1]);
         if(kv[0] == "TP_LOW_RISK") TPLowRisk = (int)StringToInteger(kv[1]);
         if(kv[0] == "TP_MED_RISK") TPMedRisk = (int)StringToInteger(kv[1]);
         if(kv[0] == "TP_HIGH_RISK") TPHighRisk = (int)StringToInteger(kv[1]);
      }
   }
}
//+------------------------------------------------------------------+