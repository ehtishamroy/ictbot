//+------------------------------------------------------------------+
//| NYAM-SWEEP-FVG v1.0 — ICT sweep -> MSS -> FVG-tap EA (MetaTrader 5)|
//| Generated from the spec (Part A/D). New-bar M5 logic only.        |
//| Function names match the D1 DEF-ID map. Port of the tested Python  |
//| engine — cross-check MT5 "real ticks" numbers vs Python before use.|
//|                                                                    |
//| STATUS: UNTESTED. No edge is claimed. Backtest ONLY in             |
//| "Every tick based on real ticks" mode.                            |
//+------------------------------------------------------------------+
#property copyright "ictbot"
#property version   "1.00"
#property strict

#include <Trade/Trade.mqh>

//==================== Inputs (A6 parameter table) ===================
input group "Free parameters (A6)"
input int    SweepCloseN      = 3;      // DEF-SWEEP-01  (range 1-5)
input int    MssWindow        = 12;     // DEF-MSS-01    (range 6-20)
input double DispMult         = 1.5;    // DEF-DISP-01   (range 1.0-2.5)
input double FvgMinATR        = 0.5;    // DEF-FVG-01    (range 0.3-1.0)
input int    ExpiryBars       = 15;     // DEF-ENTRY-01  (range 8-24)
input double SlBufferPts       = 2;     // beyond sweep_extreme (range 0-10)
input int    ServerToNYOffsetH = 7;     // DEF-TIME-01 — VERIFY per broker, never optimise

input group "Fixed constants (A6)"
input double FvgMaxATR        = 3.0;
input double DispMaxATR       = 4.0;
input int    SwingKLtf        = 1;
input int    SwingKHtf        = 2;
input int    AtrLen           = 14;
input double RiskPct          = 0.5;    // % equity per trade
input int    MaxTradesPerDay  = 2;
input double DailyStopR       = 2.0;
input int    MaxBars          = 42;     // 3.5h in M5
input double PartialClosePct  = 50.0;
input int    NewsBlockMin      = 15;    // +/- around high-impact USD/EUR
input double MaxSpreadPips     = 1.2;
input double ShallowFloorPts   = 5;
input double DolReachATR       = 3.0;

input group "Session (NY wall-clock)"
input int    KZStartHH = 8,  KZStartMM = 30;   // killzone start
input int    KZEndHH   = 11, KZEndMM   = 0;    // killzone end
input int    FlatHH    = 12, FlatMM    = 0;    // hard flat time
input int    DayBoundaryHH = 17;               // 17:00 NY trading-day boundary

input group "Misc"
input bool   UseNewsFilter = true;
input long   MagicNumber   = 20260717;

//==================== Globals =======================================
CTrade   trade;
int      atrM5Handle = INVALID_HANDLE;
int      atrH1Handle = INVALID_HANDLE;

enum ESetupState { ST_IDLE, ST_SWEPT, ST_WAIT, ST_INTRADE };
ESetupState state = ST_IDLE;

// setup carry
int      g_dir = 0;                 // +1 long, -1 short
double   g_sweepExtreme = 0.0;
double   g_sweptPool = 0.0;
int      g_sweptBars = 0;
double   g_ce = 0.0, g_sl0 = 0.0, g_tp1 = 0.0, g_tp2 = 0.0, g_riskDist = 0.0;
int      g_waitBars = 0;
ulong    g_pendingTicket = 0;

// trade carry
bool     g_tp1Hit = false;
int      g_barsInTrade = 0;
double   g_entryPrice = 0.0;

// daily guards
datetime g_curDay = 0;
int      g_tradesToday = 0;
double   g_dayR = 0.0;
bool     g_locked = false;
// one-attempt-per-pool/day: remember pools already attempted today
double   g_attemptedPools[8];
int      g_attemptedN = 0;

double   Point_() { return _Point; }
double   Pip()    { return _Point * 10.0; }   // 5-digit EURUSD: 1 pip = 10 points

//==================== Time helpers (DEF-TIME-01 / KZ-01) ============
datetime ToNY(datetime srv) { return srv - (datetime)ServerToNYOffsetH * 3600; }

void NyStruct(datetime srv, MqlDateTime &ny) { TimeToStruct(ToNY(srv), ny); }

bool InKillzone(datetime srv)
{
   MqlDateTime ny; NyStruct(srv, ny);
   int m  = ny.hour*60 + ny.min;
   int lo = KZStartHH*60 + KZStartMM;
   int hi = KZEndHH*60   + KZEndMM;
   return (m >= lo && m < hi);
}

int NyMinutes(datetime srv) { MqlDateTime ny; NyStruct(srv, ny); return ny.hour*60 + ny.min; }

// server time of the most recent 17:00-NY trading-day boundary <= srv
datetime TradingDayStart(datetime srv)
{
   MqlDateTime ny; NyStruct(srv, ny);
   datetime nyt = ToNY(srv);
   datetime midnight = nyt - (nyt % 86400);           // NY 00:00 of this NY date
   datetime boundaryNy = midnight + (datetime)DayBoundaryHH*3600;
   if(nyt < boundaryNy) boundaryNy -= 86400;          // before 17:00 -> yesterday's boundary
   return boundaryNy + (datetime)ServerToNYOffsetH*3600;   // back to server time
}

//==================== New-bar detection =============================
bool NewM5Bar()
{
   static datetime last = 0;
   datetime t = iTime(_Symbol, PERIOD_M5, 0);
   if(t == last) return false;
   last = t;
   return true;
}

//==================== Data copy helpers =============================
// Copy `count` CLOSED bars (shift 1..count) chronologically: idx 0=oldest,
// idx count-1 = last closed bar (the decision bar i).
bool CopyClosed(ENUM_TIMEFRAMES tf, int count, MqlRates &r[])
{
   ArraySetAsSeries(r, false);
   int got = CopyRates(_Symbol, tf, 1, count, r);
   return (got == count);
}

bool CopyAtr(int handle, int count, double &a[])
{
   ArraySetAsSeries(a, false);
   int got = CopyBuffer(handle, 0, 1, count, a);
   return (got == count);
}

//==================== Swings (DEF-SWING-01) =========================
bool IsSwingHigh(const MqlRates &r[], int i, int k, int n)
{
   if(i < k || i >= n-k) return false;
   double h = r[i].high;
   for(int j=1; j<=k; j++)
      if(!(h > r[i-j].high) || !(h > r[i+j].high)) return false;
   return true;
}
bool IsSwingLow(const MqlRates &r[], int i, int k, int n)
{
   if(i < k || i >= n-k) return false;
   double l = r[i].low;
   for(int j=1; j<=k; j++)
      if(!(l < r[i-j].low) || !(l < r[i+j].low)) return false;
   return true;
}
// Most recent swing high confirmed as of bar i (pivot p confirmed at p+k).
double ConfirmedSwingHigh(const MqlRates &r[], int i, int k, int n)
{
   for(int p=i-k; p>=k; p--)
      if(IsSwingHigh(r, p, k, n)) return r[p].high;
   return 0.0;
}
double ConfirmedSwingLow(const MqlRates &r[], int i, int k, int n)
{
   for(int p=i-k; p>=k; p--)
      if(IsSwingLow(r, p, k, n)) return r[p].low;
   return 0.0;
}

//==================== HTF bias (DEF-BIAS-01 / STRUCT-01/02) =========
// Walk H1 confirmed swings and track BOS/CHoCH state; return +1/-1/0.
int HtfBias(const MqlRates &r[], int n, int k)
{
   int stateS = 0;                 // 0 neutral, +1 up, -1 down
   double brokenSH = 0.0, brokenSL = 0.0;
   for(int i=0; i<n; i++)
   {
      double sh = ConfirmedSwingHigh(r, i, k, n);
      double sl = ConfirmedSwingLow(r, i, k, n);
      double c  = r[i].close;
      if(sh > 0.0 && sh != brokenSH && c > sh)
      {
         stateS = +1; brokenSH = sh;
      }
      else if(sl > 0.0 && sl != brokenSL && c < sl)
      {
         stateS = -1; brokenSL = sl;
      }
   }
   return stateS;
}

//==================== PDH/PDL (DEF-LIQ-01) ==========================
// High/low of the previous 17:00->17:00 NY trading day, scanning M5 history.
bool PrevDayLevels(const MqlRates &r[], int n, datetime nowSrv, double &pdh, double &pdl)
{
   datetime curStart  = TradingDayStart(nowSrv);
   datetime prevStart = curStart - 86400;
   double hi = -1.0, lo = -1.0;
   for(int i=0; i<n; i++)
   {
      if(r[i].time >= prevStart && r[i].time < curStart)
      {
         if(hi < 0 || r[i].high > hi) hi = r[i].high;
         if(lo < 0 || r[i].low  < lo) lo = r[i].low;
      }
   }
   if(hi < 0 || lo < 0) return false;
   pdh = hi; pdl = lo; return true;
}

// 08:30-NY open price of the current trading day (first killzone bar's open)
double KzOpen(const MqlRates &r[], int n, datetime nowSrv)
{
   datetime curStart = TradingDayStart(nowSrv);
   for(int i=0; i<n; i++)
      if(r[i].time >= curStart && InKillzone(r[i].time)) return r[i].open;
   return 0.0;
}

// has `pool` been pierced (wick) since the trading-day start, up to bar `upto`?
bool SweptSince(const MqlRates &r[], int n, datetime dayStart, int upto, double level, bool below)
{
   double tick = Point_();
   for(int i=0; i<=upto && i<n; i++)
   {
      if(r[i].time < dayStart) continue;
      if(below && r[i].low  <= level - tick) return true;
      if(!below && r[i].high >= level + tick) return true;
   }
   return false;
}

//==================== Sweep (DEF-SWEEP-01) ==========================
// Is bar i the close-back of a valid sweep of `level`? dir +1=sweep PDL, -1=PDH.
bool SweepDetected(const MqlRates &r[], int n, int i, double level, int dir,
                   double &sweepExtreme, int &penIdx)
{
   double tick = Point_();
   int lo = MathMax(0, i - SweepCloseN);
   if(dir > 0)
   {
      if(!(r[i].close > level)) return false;
      int pen = -1;
      for(int j=lo; j<=i; j++) if(r[j].low <= level - tick) { pen = j; break; }
      if(pen < 0) return false;
      for(int j=pen; j<i; j++) if(r[j].close > level) return false;   // i is first close-back
      double ext = r[pen].low;
      for(int j=pen; j<=i; j++) ext = MathMin(ext, r[j].low);
      sweepExtreme = ext; penIdx = pen; return true;
   }
   else
   {
      if(!(r[i].close < level)) return false;
      int pen = -1;
      for(int j=lo; j<=i; j++) if(r[j].high >= level + tick) { pen = j; break; }
      if(pen < 0) return false;
      for(int j=pen; j<i; j++) if(r[j].close < level) return false;
      double ext = r[pen].high;
      for(int j=pen; j<=i; j++) ext = MathMax(ext, r[j].high);
      sweepExtreme = ext; penIdx = pen; return true;
   }
}

//==================== Displacement (DEF-DISP-01) ====================
bool IsDisplacement(const MqlRates &r[], int i, double atr, int dir)
{
   if(atr <= 0.0) return false;
   double loT = DispMult * atr, hiT = DispMaxATR * atr, summed = 0.0;
   for(int run=1; run<=3; run++)
   {
      int j = i - run + 1;
      if(j < 0) break;
      double body = r[j].close - r[j].open;
      bool sameDir = (dir > 0) ? (body > 0) : (body < 0);
      if(!sameDir) break;
      double mag = MathAbs(body);
      if(mag > hiT) return false;          // single news-print candle -> reject
      summed += mag;
      if(summed >= loT) return true;
   }
   return false;
}

//==================== FVG (DEF-FVG-01) ==============================
// Returns the entry CE (0 if none) for a valid FVG formed by (i-2,i-1,i).
// Nested rule handled by MSS scanning lowest bull / highest bear.
bool DetectFVG(const MqlRates &r[], int i, double atr, int dir,
               double &bottom, double &top)
{
   if(i < 2 || atr <= 0.0) return false;
   double loB = FvgMinATR * atr, hiB = FvgMaxATR * atr;
   if(dir > 0 && r[i].low > r[i-2].high)
   {
      double b = r[i-2].high, t = r[i].low;
      if((t-b) >= loB && (t-b) <= hiB) { bottom=b; top=t; return true; }
   }
   if(dir < 0 && r[i].high < r[i-2].low)
   {
      double b = r[i].high, t = r[i-2].low;
      if((t-b) >= loB && (t-b) <= hiB) { bottom=b; top=t; return true; }
   }
   return false;
}

//==================== MSS (DEF-MSS-01) ==============================
// Close beyond confirmed opposite swing + displacement + leaves an FVG.
// Returns CE of the nested FVG (lowest bull / highest bear), 0 if none.
double MssConfirmed(const MqlRates &r[], int n, int i, int dir, double confSwing, double atr)
{
   if(confSwing <= 0.0) return 0.0;
   if(dir > 0 && !(r[i].close > confSwing)) return 0.0;
   if(dir < 0 && !(r[i].close < confSwing)) return 0.0;
   if(!IsDisplacement(r, i, atr, dir)) return 0.0;

   int start = MathMax(2, i-3);
   double bestCE = 0.0, bestKey = 0.0; bool found = false;
   for(int p=start; p<=i; p++)
   {
      double b, t;
      if(!DetectFVG(r, p, atr, dir, b, t)) continue;
      double ce = 0.5*(b+t);
      if(!found) { bestCE=ce; bestKey=ce; found=true; }
      else if(dir > 0 && ce < bestKey) { bestCE=ce; bestKey=ce; }   // lowest bull
      else if(dir < 0 && ce > bestKey) { bestCE=ce; bestKey=ce; }   // highest bear
   }
   return found ? bestCE : 0.0;
}

//==================== DOL (DEF-DOL-01) ==============================
bool DolExists(double price, double level, double atrH1, int dir, bool swept)
{
   if(swept || atrH1 <= 0.0) return false;
   double reach = DolReachATR * atrH1;
   if(dir > 0) return (level > price && (level - price) <= reach);
   return (level < price && (price - level) <= reach);
}

//==================== Filters (A5) =================================
bool SpreadOK()
{
   double spr = (double)SymbolInfoInteger(_Symbol, SYMBOL_SPREAD) * Point_();
   return spr <= MaxSpreadPips * Pip();
}
bool NewsClear(datetime srv)
{
   if(!UseNewsFilter) return true;
   datetime from = srv - (datetime)NewsBlockMin*60;
   datetime to   = srv + (datetime)NewsBlockMin*60;
   MqlCalendarValue values[];
   // pull events in window; filter USD/EUR high-impact
   string curr[2] = {"USD","EUR"};
   for(int c=0; c<2; c++)
   {
      MqlCalendarValue v[];
      if(CalendarValueHistory(v, from, to, NULL, curr[c]) <= 0) continue;
      for(int k=0; k<ArraySize(v); k++)
      {
         MqlCalendarEvent ev;
         if(!CalendarEventById(v[k].event_id, ev)) continue;
         if(ev.importance == CALENDAR_IMPORTANCE_HIGH) return false;
      }
   }
   return true;
}

//==================== Risk sizing (calc_lots, A4) ==================
double CalcLots(double slPoints)
{
   double tickVal = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSz  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double riskCash = AccountInfoDouble(ACCOUNT_EQUITY) * RiskPct / 100.0;
   double lossPerLot = slPoints * Point_() / tickSz * tickVal;
   if(lossPerLot <= 0.0) return 0.0;
   double lots = riskCash / lossPerLot;
   double minLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double step   = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   lots = MathFloor(lots/step)*step;
   return MathMax(lots, minLot);
}

//==================== Daily guards =================================
void MaybeResetDay(datetime srv)
{
   datetime dayStart = TradingDayStart(srv);
   if(dayStart != g_curDay)
   {
      g_curDay = dayStart;
      g_tradesToday = 0;
      g_dayR = 0.0;
      g_locked = false;
      g_attemptedN = 0;
   }
}
bool PoolAttempted(double pool)
{
   for(int i=0; i<g_attemptedN; i++) if(MathAbs(g_attemptedPools[i]-pool) < Point_()) return true;
   return false;
}
void MarkAttempted(double pool)
{
   if(g_attemptedN < ArraySize(g_attemptedPools)) g_attemptedPools[g_attemptedN++] = pool;
}

//==================== State reset =================================
void ResetSetup()
{
   state = ST_IDLE; g_dir = 0; g_sweepExtreme = 0; g_sweptPool = 0;
   g_sweptBars = 0; g_ce = g_sl0 = g_tp1 = g_tp2 = g_riskDist = 0;
   g_waitBars = 0;
   if(g_pendingTicket != 0) { trade.OrderDelete(g_pendingTicket); g_pendingTicket = 0; }
}

//==================== OnInit / OnDeinit ===========================
int OnInit()
{
   trade.SetExpertMagicNumber(MagicNumber);
   atrM5Handle = iATR(_Symbol, PERIOD_M5, AtrLen);
   atrH1Handle = iATR(_Symbol, PERIOD_H1, AtrLen);
   if(atrM5Handle == INVALID_HANDLE || atrH1Handle == INVALID_HANDLE)
      return INIT_FAILED;

   // DEF-TIME-01 verification aid: print NY time of a known server bar.
   datetime now = TimeCurrent();
   MqlDateTime ny; NyStruct(now, ny);
   PrintFormat("NYAM-SWEEP-FVG init. ServerToNYOffsetH=%d -> server %s maps to NY %02d:%02d. "
               "VERIFY this against a known session open before trusting results.",
               ServerToNYOffsetH, TimeToString(now, TIME_MINUTES), ny.hour, ny.min);
   return INIT_SUCCEEDED;
}
void OnDeinit(const int reason)
{
   if(atrM5Handle != INVALID_HANDLE) IndicatorRelease(atrM5Handle);
   if(atrH1Handle != INVALID_HANDLE) IndicatorRelease(atrH1Handle);
}

//==================== Position helpers ============================
bool HaveOpenPosition()
{
   for(int i=PositionsTotal()-1; i>=0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(PositionSelectByTicket(tk) && PositionGetInteger(POSITION_MAGIC)==MagicNumber
         && PositionGetString(POSITION_SYMBOL)==_Symbol)
         return true;
   }
   return false;
}

//==================== Trade management (IN_TRADE) ==================
void ManageTrade(datetime srv)
{
   if(!PositionSelect(_Symbol)) { state = ST_IDLE; return; }
   if(PositionGetInteger(POSITION_MAGIC) != MagicNumber) return;

   g_barsInTrade++;
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double vol = PositionGetDouble(POSITION_VOLUME);
   long   ptype = PositionGetInteger(POSITION_TYPE);
   bool   isLong = (ptype == POSITION_TYPE_BUY);

   // TP1: close 50% + move SL to break-even (once)
   if(!g_tp1Hit)
   {
      bool tp1 = isLong ? (bid >= g_tp1) : (ask <= g_tp1);
      if(tp1)
      {
         double closeVol = NormalizeDouble(vol * PartialClosePct/100.0, 2);
         double minLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
         if(closeVol >= minLot)
         {
            trade.PositionClosePartial(_Symbol, closeVol);
            trade.PositionModify(_Symbol, g_entryPrice, g_tp2);   // SL -> BE, TP -> TP2
            g_tp1Hit = true;
         }
      }
   }
   else
   {
      bool tp2 = isLong ? (bid >= g_tp2) : (ask <= g_tp2);
      bool be  = isLong ? (bid <= g_entryPrice) : (ask >= g_entryPrice);
      if(tp2 || be) { trade.PositionClose(_Symbol); state = ST_IDLE; PostTradeGuards(); return; }
   }

   // time exits: flat at 12:00 NY, or max_bars
   int nym = NyMinutes(srv);
   if(nym >= FlatHH*60+FlatMM || g_barsInTrade >= MaxBars)
   {
      trade.PositionClose(_Symbol);
      state = ST_IDLE; PostTradeGuards(); return;
   }
}

// Approximate per-trade R accounting for the daily guards (real R comes from
// the closed-deal history / Python cross-check; here we track for -2R lock).
void PostTradeGuards()
{
   g_tradesToday++;
   // recompute realised R for the day from history deals since day start
   double dayProfit = 0.0;
   HistorySelect(g_curDay, TimeCurrent());
   for(int i=HistoryDealsTotal()-1; i>=0; i--)
   {
      ulong tk = HistoryDealGetTicket(i);
      if(HistoryDealGetInteger(tk, DEAL_MAGIC)==MagicNumber
         && HistoryDealGetString(tk, DEAL_SYMBOL)==_Symbol)
         dayProfit += HistoryDealGetDouble(tk, DEAL_PROFIT);
   }
   double rCash = AccountInfoDouble(ACCOUNT_EQUITY) * RiskPct / 100.0;
   if(rCash > 0) g_dayR = dayProfit / rCash;
   if(g_dayR <= -DailyStopR) g_locked = true;
   MarkAttempted(g_sweptPool);              // one attempt per pool per day (A4)
   g_tp1Hit = false; g_barsInTrade = 0;
}

//==================== Main processing =============================
void Process()
{
   datetime nowSrv = iTime(_Symbol, PERIOD_M5, 1);   // last closed M5 bar time
   MaybeResetDay(nowSrv);

   if(state == ST_INTRADE) { ManageTrade(nowSrv); return; }
   if(HaveOpenPosition() && state != ST_INTRADE) return;  // safety

   int N = 600;
   MqlRates rM5[]; if(!CopyClosed(PERIOD_M5, N, rM5)) return;
   double atrM5[]; if(!CopyAtr(atrM5Handle, N, atrM5)) return;
   int i = N-1;                                   // decision bar
   double atr = atrM5[i];

   int Nh = 240;
   MqlRates rH1[]; if(!CopyClosed(PERIOD_H1, Nh, rH1)) return;
   double atrH1Buf[]; if(!CopyAtr(atrH1Handle, Nh, atrH1Buf)) return;
   double atrH1 = atrH1Buf[Nh-1];

   double pdh, pdl;
   if(!PrevDayLevels(rM5, N, nowSrv, pdh, pdl)) return;
   datetime dayStart = TradingDayStart(nowSrv);

   // entry-path guards
   bool entryOk = (!g_locked && g_tradesToday < MaxTradesPerDay
                   && g_dayR > -DailyStopR && InKillzone(rM5[i].time));

   //---------------- IDLE ----------------
   if(state == ST_IDLE)
   {
      if(!entryOk) return;
      int bias = HtfBias(rH1, Nh, SwingKHtf);
      if(bias == 0) return;
      g_dir = bias;
      double swpLvl = (g_dir > 0) ? pdl : pdh;
      double dolLvl = (g_dir > 0) ? pdh : pdl;
      if(PoolAttempted(swpLvl)) return;

      double kzOpen = KzOpen(rM5, N, nowSrv);
      if(kzOpen <= 0.0) return;
      bool shallow = (g_dir > 0) ? ((kzOpen - swpLvl) < ShallowFloorPts*Point_())
                                 : ((swpLvl - kzOpen) < ShallowFloorPts*Point_());
      if(shallow) return;

      bool dolSwept = SweptSince(rM5, N, dayStart, i, dolLvl, (g_dir < 0));
      if(!DolExists(rM5[i].close, dolLvl, atrH1, g_dir, dolSwept)) return;

      double ext; int pen;
      if(!SweepDetected(rM5, N, i, swpLvl, g_dir, ext, pen)) return;
      if(SweptSince(rM5, N, dayStart, pen-1, swpLvl, (g_dir > 0))) return;   // N3 fuel unspent

      g_sweepExtreme = ext; g_sweptPool = swpLvl; g_sweptBars = 0;
      state = ST_SWEPT;
      return;
   }

   //---------------- SWEPT ----------------
   if(state == ST_SWEPT)
   {
      if(!InKillzone(rM5[i].time)) { ResetSetup(); return; }
      g_sweptBars++;
      if(g_sweptBars > MssWindow) { ResetSetup(); return; }
      double swing = (g_dir > 0) ? ConfirmedSwingHigh(rM5, i, SwingKLtf, N)
                                 : ConfirmedSwingLow(rM5, i, SwingKLtf, N);
      double ce = MssConfirmed(rM5, N, i, g_dir, swing, atr);
      if(ce <= 0.0) return;

      g_ce = ce;
      if(g_dir > 0) { g_sl0 = g_sweepExtreme - SlBufferPts*Point_(); g_tp1 = swing; g_tp2 = pdh; }
      else          { g_sl0 = g_sweepExtreme + SlBufferPts*Point_(); g_tp1 = swing; g_tp2 = pdl; }
      g_riskDist = MathAbs(g_ce - g_sl0);
      if(g_riskDist <= 0.0) { ResetSetup(); return; }
      double rr1 = g_dir * (g_tp1 - g_ce) / g_riskDist;
      if(rr1 < 1.0) { ResetSetup(); return; }               // skip low-RR setups

      g_waitBars = 0;
      // place the limit at CE with expiry (DEF-ENTRY-01)
      if(SpreadOK() && NewsClear(rM5[i].time))
      {
         double lots = CalcLots(g_riskDist / Point_());
         datetime exp = rM5[i].time + (datetime)ExpiryBars*5*60;
         bool ok = (g_dir > 0)
            ? trade.BuyLimit(lots, g_ce, _Symbol, g_sl0, g_tp2, ORDER_TIME_SPECIFIED, exp)
            : trade.SellLimit(lots, g_ce, _Symbol, g_sl0, g_tp2, ORDER_TIME_SPECIFIED, exp);
         if(ok) { g_pendingTicket = trade.ResultOrder(); state = ST_WAIT; }
      }
      return;
   }

   //---------------- WAIT_RETRACE ----------------
   if(state == ST_WAIT)
   {
      // filled? -> position exists
      if(HaveOpenPosition())
      {
         g_pendingTicket = 0; g_entryPrice = g_ce; g_tp1Hit = false; g_barsInTrade = 0;
         state = ST_INTRADE;
         return;
      }
      g_waitBars++;
      int nym = NyMinutes(rM5[i].time);
      if(g_waitBars > ExpiryBars || nym >= KZEndHH*60+KZEndMM) { ResetSetup(); return; }
      // ran to TP1 before filling -> cancel
      bool reachedTp1 = (g_dir > 0) ? (rM5[i].high >= g_tp1) : (rM5[i].low <= g_tp1);
      if(reachedTp1) { ResetSetup(); return; }
      return;
   }
}

//==================== OnTick =====================================
void OnTick()
{
   if(!NewM5Bar()) return;
   Process();
}
//+------------------------------------------------------------------+
