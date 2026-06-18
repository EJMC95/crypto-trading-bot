#!/usr/bin/env python3
"""
Self-contained backtester for Eamon's Freqtrade strategies.
No TA-Lib / no freqtrade / no network. Computes EMA/RSI/ATR directly and
applies freqtrade-style fill ordering (per candle: stoploss -> ROI -> exit signal).

Compares:
  A) Daily trend filter (V4: 50/200 EMA golden/death cross) vs buy & hold  [Binance daily, 2023-2026]
  B) Intraday: buy&hold vs DayTraderV1Aggro (ungated 5m) vs V5 (same entries, daily-regime gated)
                                                                          [Kraken 5m, Dec2025-Jun2026]
"""
import pandas as pd, numpy as np, glob, os

DATA = os.environ.get("DATA_DIR", "/sessions/keen-wizardly-darwin/mnt/Crypto Trading Bot/data")

# ---------- indicators ----------
def ema(s, n):           return s.ewm(span=n, adjust=False).mean()
def sma(s, n):           return s.rolling(n).mean()
def rsi(s, n=14):
    d = s.diff()
    up = d.clip(lower=0); dn = -d.clip(upper=0)
    ru = up.ewm(alpha=1/n, adjust=False).mean()
    rd = dn.ewm(alpha=1/n, adjust=False).mean()
    rs = ru / rd.replace(0, np.nan)
    return (100 - 100/(1+rs)).fillna(50)
def atr(df, n=14):
    h,l,c = df['high'], df['low'], df['close']
    pc = c.shift(1)
    tr = pd.concat([h-l, (h-pc).abs(), (l-pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1/n, adjust=False).mean()

def load(ex, pair, tf):
    return pd.read_feather(f"{DATA}/{ex}/{pair}-{tf}.feather").set_index('date')

def metrics(equity, trades_pnl, periods_per_year):
    eq = np.asarray(equity, float)
    total = eq[-1]/eq[0]-1
    peak = np.maximum.accumulate(eq)
    maxdd = ((eq-peak)/peak).min()
    rets = np.diff(eq)/eq[:-1]
    sharpe = (rets.mean()/rets.std()*np.sqrt(periods_per_year)) if rets.std()>0 else 0
    wins = [p for p in trades_pnl if p>0]; losses=[p for p in trades_pnl if p<=0]
    wr = len(wins)/len(trades_pnl) if trades_pnl else 0
    pf = (sum(wins)/abs(sum(losses))) if losses and sum(losses)!=0 else float('inf')
    return dict(total=total, maxdd=maxdd, sharpe=sharpe, n=len(trades_pnl), wr=wr, pf=pf)

# ============================================================== #
# A) DAILY TREND FILTER (V4) vs BUY & HOLD                        #
# ============================================================== #
def daily_trend(pair, fee=0.001, fast=50, slow=200):
    df = load('binance', pair, '1d').copy()
    df['ef']=ema(df['close'],fast); df['es']=ema(df['close'],slow)
    df['long'] = (df['ef']>df['es']).astype(int)
    # Enforce startup maturity: the slow EMA is meaningless until `slow` candles
    # have passed. Drop that head so both V4 and buy&hold start on the same matured bar.
    df = df.iloc[slow:].copy()
    pos=0; cash=1.0; coin=0.0; eq=[]; entry=None; tp=[]
    px=df['close'].values; sig=df['long'].values
    for i in range(len(df)):
        p=px[i]
        # act on yesterday's signal at today's open≈close (daily, enter/exit at close)
        if pos==0 and sig[i]==1:
            coin = cash*(1-fee)/p; cash=0; pos=1; entry=p
        elif pos==1 and sig[i]==0:
            cash = coin*p*(1-fee); coin=0; pos=0
            tp.append(p/entry*(1-fee)**2-1)
        eq.append(cash + coin*p)
    if pos==1: tp.append(px[-1]/entry*(1-fee)**2-1)
    m=metrics(eq, tp, 365)
    bh = px[-1]/px[0]-1
    bh_eq = px/px[0]; bh_peak=np.maximum.accumulate(bh_eq); bh_dd=((bh_eq-bh_peak)/bh_peak).min()
    return m, bh, bh_dd, df.index[0], df.index[-1]

# ============================================================== #
# B) INTRADAY 5m: ungated DayTrader vs daily-regime-gated V5      #
# ============================================================== #
def build_5m(pair):
    d5 = load('kraken', pair, '5m').copy()
    d1h = load('kraken', pair, '1h').copy()
    # 5m indicators (DayTraderV1Aggro defaults)
    d5['ema_fast']=ema(d5['close'],9); d5['ema_slow']=ema(d5['close'],21)
    d5['rsi']=rsi(d5['close'],14); d5['vol_sma']=sma(d5['volume'],20)
    d5['atr']=atr(d5,14)
    # 1h informative trend filter
    d1h['ema9']=ema(d1h['close'],9); d1h['ema9_rising']=(d1h['ema9']>d1h['ema9'].shift(1))
    inf=d1h[['close','ema9','ema9_rising']].rename(columns={'close':'close_1h','ema9':'ema9_1h','ema9_rising':'ema9_rising_1h'})
    d5=d5.join(inf.reindex(d5.index, method='ffill'))
    # daily regime from Binance daily 50/200 (the V4 gate), aligned by date
    db=load('binance', pair, '1d').copy()
    db['ef']=ema(db['close'],50); db['es']=ema(db['close'],200)
    db['regime_up']=(db['ef']>db['es'])
    db=db.iloc[200:].copy()        # enforce 200-day maturity before using the regime
    reg=db['regime_up'].reindex(d5.index, method='ffill').fillna(False)
    d5['regime_up']=reg.values
    return d5.dropna()

def backtest_5m(df, gated, fee=0.0026,
                roi={0:0.04,30:0.025,60:0.015,120:0.008}, hard_sl=-0.12, atr_mult=1.5):
    o,h,l,c = df['open'].values,df['high'].values,df['low'].values,df['close'].values
    ef,es,rs = df['ema_fast'].values,df['ema_slow'].values,df['rsi'].values
    vol,vsma = df['volume'].values, df['vol_sma'].values
    c1h,e1h,rise1h = df['close_1h'].values,df['ema9_1h'].values,df['ema9_rising_1h'].values
    atrv = df['atr'].values
    regime = df['regime_up'].values
    idx = df.index
    roi_items = sorted(roi.items())
    def roi_thresh(mins):
        t=roi_items[0][1]
        for m,v in roi_items:
            if mins>=m: t=v
        return t
    cash=1.0; coin=0.0; pos=0; entry_px=0.0; entry_t=None; peak=0.0; tp=[]; eq=[]
    for i in range(len(df)):
        price=c[i]
        if pos==1:
            # 1) stoploss on low (hard + ATR trailing)
            atr_stop = -(atr_mult*atrv[i])/price if price>0 else hard_sl
            stop_frac = max(atr_stop, hard_sl)          # closer to 0 of the two? freqtrade: never wider than hard
            stop_price = entry_px*(1+stop_frac)
            exited=False
            if l[i] <= stop_price:
                fill=stop_price; cash=coin*fill*(1-fee); coin=0; pos=0
                tp.append(fill/entry_px*(1-fee)**2-1); exited=True
            if not exited:
                # 2) ROI on high
                mins=(idx[i]-entry_t).total_seconds()/60
                thr=roi_thresh(mins)
                roi_price=entry_px*(1+thr)
                if h[i]>=roi_price:
                    fill=roi_price; cash=coin*fill*(1-fee); coin=0; pos=0
                    tp.append(fill/entry_px*(1-fee)**2-1); exited=True
            if not exited:
                # 3) exit signal on close (ema_fast<ema_slow)
                if ef[i]<es[i]:
                    fill=price; cash=coin*fill*(1-fee); coin=0; pos=0
                    tp.append(fill/entry_px*(1-fee)**2-1); exited=True
        if pos==0:
            entry_sig = (ef[i]>es[i]) and (rs[i]>55) and (vol[i]>vsma[i]) \
                        and (c1h[i]>e1h[i]) and bool(rise1h[i]) and (vol[i]>0)
            if gated:
                entry_sig = entry_sig and bool(regime[i])
            if entry_sig:
                coin=cash*(1-fee)/price; cash=0; pos=1
                entry_px=price; entry_t=idx[i]
        eq.append(cash+coin*price)
    if pos==1: tp.append(c[-1]/entry_px*(1-fee)**2-1)
    m=metrics(eq, tp, 365*24*12)
    return m, eq

def pct(x): return f"{x*100:+.1f}%"
def main():
    print("="*78)
    print("A) DAILY TREND FILTER (V4: 50/200 EMA cross)  vs  BUY & HOLD   [Binance daily]")
    print("="*78)
    for pair in ['BTC_USDT','ETH_USDT']:
        m,bh,bhdd,d0,d1=daily_trend(pair)
        print(f"\n{pair}   {d0.date()} -> {d1.date()}")
        print(f"  Buy & hold     return {pct(bh):>8}   maxDD {pct(bhdd):>7}")
        print(f"  V4 trend filt  return {pct(m['total']):>8}   maxDD {pct(m['maxdd']):>7}"
              f"   trades {m['n']}  win {m['wr']*100:.0f}%  Sharpe {m['sharpe']:.2f}")
    print("\n" + "="*78)
    print("B) INTRADAY 5m  [Kraken, Dec 2025 -> Jun 2026, fee 0.26%/side taker]")
    print("   ungated DayTraderV1Aggro  vs  V5 (same entries + daily-regime gate)")
    print("="*78)
    for pair in ['BTC_USDT','ETH_USDT']:
        df=build_5m(pair)
        d0,d1=df.index[0],df.index[-1]
        bh=df['close'].iloc[-1]/df['close'].iloc[0]-1
        reg_up_pct=df['regime_up'].mean()*100
        print(f"\n{pair}   {d0.date()} -> {d1.date()}   (daily regime 'up' {reg_up_pct:.0f}% of the window)")
        print(f"  Buy & hold                       return {pct(bh):>8}")
        for fee in (0.0010, 0.0026):
            mu,_=backtest_5m(df, gated=False, fee=fee)
            mg,_=backtest_5m(df, gated=True,  fee=fee)
            print(f"  -- fee {fee*100:.2f}%/side --")
            print(f"  DayTraderV1Aggro (ungated/live)  return {pct(mu['total']):>8}   maxDD {pct(mu['maxdd']):>7}"
                  f"   trades {mu['n']:>4}  win {mu['wr']*100:.0f}%  PF {mu['pf']:.2f}")
            print(f"  V5 regime-gated                  return {pct(mg['total']):>8}   maxDD {pct(mg['maxdd']):>7}"
                  f"   trades {mg['n']:>4}  win {mg['wr']*100:.0f}%  PF {mg['pf']:.2f}")
    print()

if __name__=="__main__":
    main()
