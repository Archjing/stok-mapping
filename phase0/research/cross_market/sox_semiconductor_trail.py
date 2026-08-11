import sqlite3, sys, os
sys.path.insert(0, "/Users/aj/workspace/stok-mapping")
sys.path.insert(0, "/tmp/.venv-backtest/lib/python3.12/site-packages")
import pandas as pd; import numpy as np

from phase0.execution.accounts import SimulatedAccountConfig, _trade_cost, _affordable_buy_shares, _execution_price, _round_price_to_tick, round_lot_floor

# ── 账户配置: ETF 真实成本 ──
account = SimulatedAccountConfig(
    account_id="backtest_512480",
    name="512480映射回测",
    initial_cash=100_000.0,
    ledger_path="/dev/null",
    database_path="/dev/null",
    execution_price_mode="next_open",
    price_tick=0.001,
    lot_size=100,
    commission=0.00025,
    stamp_duty_sell=0.0,
    slippage=0.0001,
    min_commission=5.0,
    transfer_fee_rate=0.0,
    enable_limit_check=False,   # ETF很少涨停
    enable_suspension_check=False,
    enable_t_plus_one=True,
    enable_special_limit_rules=False,
)

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

TRAIL = 0.98; TRAIL_EXT = 0.975; INIT=100_000; LOT=100

def backtest(merged, mode, use_cost):
    """mode: 'raw'|'trail'|'flex'"""
    cash=float(INIT); shares=0.0; nav=[]; state='idle'
    sell_on=None; held_days=0; extended=False
    
    for i, dt in enumerate(merged.index):
        row = merged.loc[dt]
        
        # 卖出
        if state=='holding' and i==sell_on:
            if mode=='raw':
                sp = row['close']; should_sell=True
            elif mode=='trail':
                day_bars = mins[mins['date']==dt.date()]
                if len(day_bars)==0: sp=row['close']
                else:
                    rh=day_bars.iloc[0]['open']; triggered=False
                    for _,bar in day_bars.iterrows():
                        if bar['high']>rh: rh=bar['high']
                        if bar['low']<=rh*TRAIL: sp=rh*TRAIL; triggered=True; break
                    if not triggered: sp=day_bars.iloc[-1]['close']
                should_sell=True
            elif mode=='flex':
                day_bars = mins[mins['date']==dt.date()]
                trail_c = TRAIL_EXT if extended else TRAIL
                if len(day_bars)==0: cat='no_data'
                else:
                    rh=day_bars.iloc[0]['open']; triggered=False
                    for _,bar in day_bars.iterrows():
                        if bar['high']>rh: rh=bar['high']
                        if bar['low']<=rh*trail_c: sp_trigger=rh*trail_c; triggered=True; break
                    if triggered: cat='A_trail'
                    else:
                        dh=day_bars['high'].max(); cp=day_bars.iloc[-1]['close']
                        if dh/cp-1<0.005 and dh/row['open']-1>0.02: cat='B_momentum'
                        elif dh/row['open']-1<0.01: cat='C_flat'
                        else: cat='D_mild'
                if cat=='A_trail': sp=sp_trigger; should_sell=True
                elif cat=='B_momentum' and held_days<3:
                    extended=True; held_days+=1; should_sell=False
                    if i+1<len(merged): sell_on=i+1
                else: sp=row['close']; should_sell=True
            else:
                sp=row['close']; should_sell=True
            
            if should_sell:
                gross = shares*sp
                cost = _trade_cost(gross, 'sell', account) if use_cost else 0.0
                cash += gross - cost; shares=0.0; state='idle'
                held_days=0; extended=False
        
        # 买入
        if state=='idle' and row['SOX_ret']>0.005 and row['VIX']<19:
            bp = row['open']
            price_row = {'open': bp, 'close': row['close']}
            ep = _execution_price(price_row, 'buy', account)
            max_shares = _affordable_buy_shares(cash_asset=cash, price=ep, requested_shares=1e9, account=account)
            if max_shares > 0:
                gross = max_shares * ep
                cost = _trade_cost(gross, 'buy', account) if use_cost else 0.0
                cash -= gross + cost; shares = max_shares; state='holding'
                if i+1<len(merged): sell_on=i+1
                held_days=1
        
        nav.append(cash + shares*row['close'])
    
    eq=np.array(nav); r=eq[1:]/eq[:-1]-1
    return eq[-1]/INIT-1, r.mean()/r.std()*np.sqrt(252), (pd.Series(eq)/pd.Series(eq).cummax()-1).min()

# ═══════════════════════════════════════════════
print(f"样本: {m.index[0].date()} → {m.index[-1].date()}, {len(m)} 天")
print(f"成本: 佣金万分之2.5(最低5元)+滑点0.01%, ETF免印花税/过户费\n")
print(f"{'策略':<30} {'收益':>8} {'年化':>8} {'夏普':>6} {'回撤':>8}")
print("-"*65)

for label, mode, cost in [('open→close (零成本)', 'raw', False),
                           ('open→close (真实成本)', 'raw', True),
                           ('2%追踪止损 (零成本)', 'trail', False),
                           ('2%追踪止损 (真实成本)', 'trail', True),
                           ('灵活持有 (零成本)', 'flex', False),
                           ('灵活持有 (真实成本)', 'flex', True)]:
    ret,sh,mdd = backtest(m, mode, cost)
    ann=(1+ret)**(1/4.5)-1
    print(f"{label:<30} {ret:>+7.1%} {ann:>+7.1%} {sh:>6.2f} {mdd:>7.1%}")

hs_ret=m['HS300'].iloc[-1]/m['HS300'].iloc[0]-1
hs_r=m['HS300'].pct_change().dropna()
print(f"{'沪深300 buy&hold':<30} {hs_ret:>+7.1%} {(1+hs_ret)**(1/4.5)-1:>+7.1%} {hs_r.mean()/hs_r.std()*np.sqrt(252):>6.2f} {'-':>8}")

us_db.close(); etf_db.close(); cn_db.close()
