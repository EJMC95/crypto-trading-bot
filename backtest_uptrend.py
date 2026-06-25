#!/usr/bin/env python3
"""
Uptrend / full-cycle backtest for the REGIME-GATED DayTraderV5 logic.

Replicates the *live* DayTraderV5Gated entry (regime_ok & momentum_ok) and exit
(EMA cross / ROI ladder / ATR + hard stop) exactly, but runs it on 1h candles
(Binance, 2023-06 -> 2026-06) so we can measure behaviour across BULL and BEAR
regimes — the 5m Kraken data only covers the Dec2025->Jun2026 bear.

Compares, per window:
  * Buy & hold
  * Ungated (momentum only)  -- the pattern that lost ~-99% in the bear
  * Regime-gated (live fix)  -- only long when daily regime up OR 1h trend rising
No freqtrade / TA-Lib / network. Honest taker fees applied per side.
"""
import pandas as pd, numpy as np, os, sys

DATA = os.environ.get("DATA_DIR", os.path.join(os.path.dirname(__file__), "data"))

def ema(s, n): return s.ewm(span=n, adjust=False).mean()
def sma(s, n): return s.rolling(n).mean()
def rsi(s, n=14):
    d = s.diff(); up = d.clip(lower=0); dn = -d.clip(upper=0)
    ru = up.ewm(alpha=1/n, adjust=False).mean(); rd = dn.ewm(alpha=1/n, adjust=False).mean()
    rs = ru / rd.replace(0, np.nan)
    return (100 - 100/(1+rs)).fillna(50)
def atr(df, n=14):
    h,l,c = df['high'],df['low'],df['close']; pc=c.shift(1)
    tr = pd.concat([h-l,(h-pc).abs(),(l-pc).abs()],axis=1).max(axis=1)
    return tr.ewm(alpha=1/n, adjust=False).mean()

def load(ex, pair, tf):
    return pd.read_feather(f"{DATA}/{ex}/{pair}-{tf}.feather").set_index('date')

def metrics(equity, tp, ppy):
    eq=np.asarray(equity,float)
    if len(eq)<2: return dict(total=0,maxdd=0,sharpe=0,n=0,wr=0,pf=float('inf'))
    total=eq[-1]/eq[0]-1
    peak=np.maximum.accumulate(eq); maxdd=((eq-peak)/peak).min()
    rets=np.diff(eq)/eq[:-1]; sharpe=(rets.mean()/rets.std()*np.sqrt(ppy)) if rets.std()>0 else 0
    wins=[p for p in tp if p>0]; losses=[p for p in tp if p<=0]
    wr=len(wins)/len(tp) if tp else 0
    pf=(sum(wins)/abs(sum(losses))) if losses and sum(losses)!=0 else float('inf')
    return dict(total=total,maxdd=maxdd,sharpe=sharpe,n=len(tp),wr=wr,pf=pf)

def build_1h(pair):
    d = load('binance', pair, '1h').copy()
    d['ema_fast']=ema(d['close'],9); d['ema_slow']=ema(d['close'],21)
    d['rsi']=rsi(d['close'],14); d['atr']=atr(d,14)
    # 1h trend filter == the strategy's "informative" ema9 rising
    d['ema9']=ema(d['close'],9); d['ema9_rising']=(d['ema9']>d['ema9'].shift(1))
    # daily regime (live softened gate): 50>200 EMA OR price reclaimed the 200d
    db=load('binance', pair, '1d').copy()
    db['rf']=ema(db['close'],50); db['rs']=ema(db['close'],200)
    db['regime_up']=((db['rf']>db['rs']) | (db['close']>db['rs']))
    db=db.iloc[200:].copy()
    d['regime_up']=db['regime_up'].reindex(d.index, method='ffill').fillna(False).values
    return d.dropna()

def run(df, gated, fee=0.0010,
        roi={0:0.02,60:0.012,180:0.006,360:0.003,720:0.0}, hard_sl=-0.12, atr_mult=1.5):
    o,h,l,c=df['open'].values,df['high'].values,df['low'].values,df['close'].values
    ef,es,rs=df['ema_fast'].values,df['ema_slow'].values,df['rsi'].values
    rise1h=df['ema9_rising'].values; atrv=df['atr'].values; regime=df['regime_up'].values
    idx=df.index; roi_items=sorted(roi.items())
    def roi_thr(mins):
        t=roi_items[0][1]
        for m,v in roi_items:
            if mins>=m: t=v
        return t
    cash=1.0; coin=0.0; pos=0; epx=0.0; et=None; tp=[]; eq=[]
    for i in range(len(df)):
        price=c[i]
        if pos==1:
            atr_stop=-(atr_mult*atrv[i])/price if price>0 else hard_sl
            stop_frac=max(atr_stop, hard_sl); stop_price=epx*(1+stop_frac); exited=False
            if l[i]<=stop_price:
                fill=stop_price; cash=coin*fill*(1-fee); coin=0; pos=0
                tp.append(fill/epx*(1-fee)**2-1); exited=True
            if not exited:
                mins=(idx[i]-et).total_seconds()/60; thr=roi_thr(mins); rp=epx*(1+thr)
                if h[i]>=rp:
                    fill=rp; cash=coin*fill*(1-fee); coin=0; pos=0
                    tp.append(fill/epx*(1-fee)**2-1); exited=True
            if not exited and ef[i]<es[i]:
                fill=price; cash=coin*fill*(1-fee); coin=0; pos=0
                tp.append(fill/epx*(1-fee)**2-1); exited=True
        if pos==0:
            # LIVE V5 entry: regime_ok = regime_up OR 1h-ema9 rising ; momentum_ok = rsi>50 OR (rsi>40 & close>ema_fast)
            regime_ok = bool(regime[i]) or bool(rise1h[i])
            momentum_ok = (rs[i]>50) or (rs[i]>40 and price>ef[i])
            sig = momentum_ok and (df['volume'].values[i]>0)
            if gated: sig = sig and regime_ok
            if sig:
                coin=cash*(1-fee)/price; cash=0; pos=1; epx=price; et=idx[i]
        eq.append(cash+coin*price)
    if pos==1: tp.append(c[-1]/epx*(1-fee)**2-1)
    return metrics(eq, tp, 365*24)

def run_trend(df, fee=0.0010, fast=50, slow=200, atr_trail=3.0):
    """EXPERT FIX candidate: trade rarely, ride the trend.
    Enter long only when fast-EMA > slow-EMA AND daily regime up (no RSI noise,
    no churn ROI ladder). Exit on EMA cross-down OR an ATR trailing stop off the
    high-water mark. Goal: few trades, winners run, fees negligible."""
    c=df['close'].values; h=df['high'].values; l=df['low'].values
    ef=ema(df['close'],fast).values; es=ema(df['close'],slow).values
    atrv=df['atr'].values; regime=df['regime_up'].values; idx=df.index
    cash=1.0; coin=0.0; pos=0; epx=0.0; peak=0.0; tp=[]; eq=[]
    for i in range(len(df)):
        price=c[i]
        if pos==1:
            peak=max(peak, h[i])
            trail=peak-atr_trail*atrv[i]
            exited=False
            if l[i]<=trail:
                fill=min(trail, price); cash=coin*fill*(1-fee); coin=0; pos=0
                tp.append(fill/epx*(1-fee)**2-1); exited=True
            if not exited and ef[i]<es[i]:
                cash=coin*price*(1-fee); coin=0; pos=0
                tp.append(price/epx*(1-fee)**2-1); exited=True
        if pos==0 and ef[i]>es[i] and bool(regime[i]):
            coin=cash*(1-fee)/price; cash=0; pos=1; epx=price; peak=h[i]
        eq.append(cash+coin*price)
    if pos==1: tp.append(c[-1]/epx*(1-fee)**2-1)
    return metrics(eq, tp, 365*24)

def pct(x): return f"{x*100:+.1f}%"

WINDOWS = [
    ("FULL CYCLE 2023-06 -> 2026-06", None, None),
    ("BULL  2023-10 -> 2024-03",      "2023-10-01", "2024-03-31"),
    ("BULL  2024-09 -> 2025-01",      "2024-09-01", "2025-01-31"),
    ("BEAR  2025-12 -> 2026-06",      "2025-12-01", "2026-06-15"),
]

def main():
    for pair in ['BTC_USDT','ETH_USDT']:
        full=build_1h(pair)
        print("="*86)
        print(f"{pair}  — gated DayTraderV5 (live logic) on 1h candles, fee 0.10%/side")
        print("="*86)
        for label,a,b in WINDOWS:
            df = full if a is None else full.loc[a:b]
            if len(df)<300:
                print(f"\n{label}: insufficient data"); continue
            bh=df['close'].iloc[-1]/df['close'].iloc[0]-1
            reg=df['regime_up'].mean()*100
            mu=run(df, gated=False); mg=run(df, gated=True); mt=run_trend(df)
            print(f"\n{label}   (regime 'up' {reg:.0f}% of window)")
            print(f"  Buy & hold       {pct(bh):>8}")
            print(f"  Ungated scalp    {pct(mu['total']):>8}   maxDD {pct(mu['maxdd']):>7}   trades {mu['n']:>4}  win {mu['wr']*100:.0f}%  PF {mu['pf']:.2f}  Sharpe {mu['sharpe']:.2f}")
            print(f"  Regime-GATED     {pct(mg['total']):>8}   maxDD {pct(mg['maxdd']):>7}   trades {mg['n']:>4}  win {mg['wr']*100:.0f}%  PF {mg['pf']:.2f}  Sharpe {mg['sharpe']:.2f}")
            print(f"  TREND-FOLLOW fix {pct(mt['total']):>8}   maxDD {pct(mt['maxdd']):>7}   trades {mt['n']:>4}  win {mt['wr']*100:.0f}%  PF {mt['pf']:.2f}  Sharpe {mt['sharpe']:.2f}")
        print()

if __name__=="__main__":
    main()
