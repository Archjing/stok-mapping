import sqlite3, sys
sys.path.insert(0, "/Users/aj/workspace/stok-mapping")
from phase0.execution.accounts import SimulatedAccountConfig, _trade_cost, _affordable_buy_shares
import pandas as pd; import numpy as np

def load_series(db, symbol):
    df = pd.read_sql(f"SELECT date,close FROM us_daily_bars WHERE symbol='{symbol}' ORDER BY date", db)
    df['date'] = pd.to_datetime(df['date']); return df.set_index('date')['close']

us_db = sqlite3.connect("/Users/aj/workspace/stok-mapping/data/us_market_history.sqlite")
sox,vix = load_series(us_db,'^SOX'),load_series(us_db,'^VIX')
us = pd.DataFrame({'SOX':sox,'VIX':vix}).dropna()
us['SOX_ret'] = us['SOX'].pct_change(); us=us[['SOX_ret','VIX']].dropna()

etf_db = sqlite3.connect("/Users/aj/workspace/stok-mapping/data/etf_history.sqlite")
daily = pd.read_sql("SELECT date,open,high,low,close FROM market_etf_daily_bars WHERE symbol='SH.512480' ORDER BY date", etf_db)
daily['date']=pd.to_datetime(daily['date']); daily=daily.set_index('date')
mins = pd.read_sql("SELECT time,open,high,low,close FROM market_etf_5min_bars WHERE symbol='SH.512480' ORDER BY time", etf_db)
mins['time']=pd.to_datetime(mins['time']); mins['date']=mins['time'].dt.date; mins=mins.set_index('time')

cn_db = sqlite3.connect("/Users/aj/workspace/stok-mapping/data/a_share_history.sqlite")
hs = pd.read_sql("SELECT date,close FROM market_index_bars WHERE symbol='SH.000300' ORDER BY date", cn_db)
hs['date']=pd.to_datetime(hs['date']); hs=hs.set_index('date')

us_s = us.copy(); us_s.index += pd.Timedelta(days=1)
m = daily[['open','high','low','close']].join(us_s,how='inner').dropna()
m = m[m.index <= pd.Timestamp('2025-12-31')]
m = m.join(hs['close'].rename('HS300'), how='inner')

print(f"样本: {m.index[0].date()} → {m.index[-1].date()}, {len(m)} 天")

# ═══════════════════════════════════════════════
# 分桶统计
# ═══════════════════════════════════════════════
signal_days = m[(m['SOX_ret']>0.005) & (m['VIX']<19)]
print(f"\n信号日: {len(signal_days)}")

for lo, hi, label in [(0.005,0.01,'0.5-1.0%'),(0.01,0.015,'1.0-1.5%'),(0.015,0.03,'1.5-3.0%'),(0.03,0.10,'>3.0%')]:
    sub = signal_days[(signal_days['SOX_ret']>lo) & (signal_days['SOX_ret']<=hi)]
    drawdowns = []
    for dt in sub.index:
        day_bars = mins[mins['date']==dt.date()]
        if len(day_bars)==0: continue
        drawdowns.append((day_bars['low'].min()/day_bars.iloc[0]['open']-1)*100)
    if drawdowns:
        dd=np.array(drawdowns)
        print(f"  {label}: {len(dd)}个, open→low均值{dd.mean():+.2f}% 中位{np.median(dd):+.2f}%, P25={np.percentile(dd,25):+.2f}%")

# 限价单策略: SOX 0.5-1.0% → 挂 open×0.99; >1.0% → 开盘追
print(f"\n限价单触及率:")
for lo, hi, label, disc in [(0.005,0.01,'0.5-1.0%',0.01),(0.01,0.015,'1.0-1.5%',0.005)]:
    sub = signal_days[(signal_days['SOX_ret']>lo) & (signal_days['SOX_ret']<=hi)]
    hit = 0; total = 0
    for dt in sub.index:
        day_bars = mins[mins['date']==dt.date()]
        if len(day_bars)==0: continue
        if day_bars['low'].min() <= m.loc[dt,'open']*(1-disc):
            hit += 1
        total += 1
    print(f"  {label} 挂open×{1-disc:.3f}: {hit}/{total} ({hit/total:.0%})")

# ═══════════════════════════════════════════════
# 回测
# ═══════════════════════════════════════════════
account = SimulatedAccountConfig(
    account_id="test", name="test", initial_cash=100_000.0,
    ledger_path="/dev/null", database_path="/dev/null",
    execution_price_mode="next_open", price_tick=0.001, lot_size=100,
    commission=0.00025, stamp_duty_sell=0.0, slippage=0.0001,
    min_commission=5.0, transfer_fee_rate=0.0,
    enable_limit_check=False, enable_suspension_check=False,
    enable_t_plus_one=True, enable_special_limit_rules=False,
)

TRAIL=0.98; INIT=100_000

def backtest(merged, use_limit):
    cash=float(INIT); shares=0.0; nav=[]; state='idle'; sell_on=None
    for i, dt in enumerate(merged.index):
        row = merged.loc[dt]
        if state=='holding' and i==sell_on:
            day_bars=mins[mins['date']==dt.date()]
            if len(day_bars)==0: sp=row['close']
            else:
                rh=day_bars.iloc[0]['open']; triggered=False
                for _,bar in day_bars.iterrows():
                    if bar['high']>rh: rh=bar['high']
                    if bar['low']<=rh*TRAIL: sp=rh*TRAIL; triggered=True; break
                if not triggered: sp=day_bars.iloc[-1]['close']
            gross=shares*sp; cost=_trade_cost(gross,'sell',account)
            cash+=gross-cost; shares=0.0; state='idle'
        if state=='idle' and row['SOX_ret']>0.005 and row['VIX']<19:
            if use_limit and row['SOX_ret'] <= 0.01:
                bp_target = row['open'] * 0.99
                day_bars = mins[mins['date']==dt.date()]
                if len(day_bars)>0 and day_bars['low'].min() <= bp_target:
                    bp = bp_target
                else:
                    bp = row['open']
            else:
                bp = row['open']
            ep = bp  # 简化: 直接用 bp
            max_s = _affordable_buy_shares(cash_asset=cash, price=ep, requested_shares=1e9, account=account)
            if max_s>0:
                gross=max_s*ep; cost=_trade_cost(gross,'buy',account)
                cash-=gross+cost; shares=max_s; state='holding'
                if i+1<len(merged): sell_on=i+1
        nav.append(cash+shares*row['close'])
    eq=np.array(nav); r=eq[1:]/eq[:-1]-1
    return eq[-1]/INIT-1, r.mean()/r.std()*np.sqrt(252), (pd.Series(eq)/pd.Series(eq).cummax()-1).min()

print(f"\n{'='*55}")
print(f"{'策略':<28} {'收益':>8} {'年化':>8} {'夏普':>6} {'回撤':>8}")
print("-"*55)
for label, ul in [('开盘买入', False), ('限价买入(弱信号挂单)', True)]:
    ret,sh,mdd = backtest(m, ul)
    ann=(1+ret)**(1/4.5)-1
    print(f"{label:<28} {ret:>+7.1%} {ann:>+7.1%} {sh:>6.2f} {mdd:>7.1%}")

hs_ret=m['HS300'].iloc[-1]/m['HS300'].iloc[0]-1
print(f"{'沪深300 buy&hold':<28} {hs_ret:>+7.1%} {(1+hs_ret)**(1/4.5)-1:>+7.1%} {'-':>6} {'-':>8}")

us_db.close(); etf_db.close(); cn_db.close()
