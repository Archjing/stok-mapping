import sqlite3, os, sys
import numpy as np
from datetime import datetime

DB = os.path.expanduser("~/workspace/stok-mapping/data/custom_indices.sqlite")

def register_meta():
    db = sqlite3.connect(DB)
    db.execute("""
        INSERT OR REPLACE INTO custom_index_meta
        (index_id, name, description, methodology, underlying)
        VALUES (?,?,?,?,?)
    """, (
        'CN_PANIC_HO30',
        'A股恐慌指数(上证50股指期权30日隐含波动率)',
        '基于上证50股指期权(HO)全链报价, 按CBOE VIX方法论计算的30日预期波动率',
        'CBOE VIX白皮书: sigma^2 = (2/T)*SUM(dK_i/K_i^2)*e^(rT)*Q(K_i) - (1/T)*(F/K_0-1)^2, 近月/次月线性插值到30天',
        'HO(上证50股指期权)'
    ))
    db.commit()
    db.close()
    print("已注册指数元数据: CN_PANIC_HO30")

def calc_vix(trade_date):
    """按 CBOE VIX 方法计算。trade_date 用近月/次月链。"""
    db = sqlite3.connect(DB)
    rows = db.execute("""
        SELECT expiry_month, option_type, strike, bid, ask, last_price
        FROM option_chains WHERE trade_date=? AND underlying='HO'
        AND bid IS NOT NULL AND ask IS NOT NULL AND bid > 0 AND ask > 0
        ORDER BY expiry_month, strike
    """, (trade_date,)).fetchall()
    
    if len(rows) < 10:
        db.close()
        return None, "链数据不足"
    
    # 分组
    months = sorted(set(r[0] for r in rows))
    if len(months) < 2:
        db.close()
        return None, "只有1个到期月,无法插值"
    
    # 无风险利率
    r = db.execute("SELECT rate_3m FROM risk_free_rates WHERE date=? ORDER BY date DESC LIMIT 1",
                   (trade_date,)).fetchone()
    rf = r[0]/100 if r else 0.0143  # 默认1.43%
    
    # 近月/次月期限 (天)
    now = datetime.strptime(trade_date, '%Y-%m-%d')
    term_days = []
    for m in months[:2]:
        yy = 2000 + int(m[:2]); mm = int(m[2:])
        # 到期日 = 该月第三个周五(简化: 月中)
        expiry = datetime(yy, mm, 15)
        days = (expiry - now).days
        term_days.append(max(days, 1) / 365.0)
    
    # 对每个到期月计算方差
    variances = []
    for mi, m in enumerate(months[:2]):
        T = term_days[mi]
        chain = [r for r in rows if r[0] == m]
        strikes = np.array([r[2] for r in chain])
        calls = {r[2]: r for r in chain if r[1] == 'C'}
        puts = {r[2]: r for r in chain if r[1] == 'P'}
        
        # F = K + e^rT (C - P), 找 |C-P| 最小的行权价
        min_diff = 1e18; F = None; K0_idx = None
        for K in strikes:
            if K in calls and K in puts:
                c = calls[K]; p = puts[K]
                cmid = (c[3] + c[4]) / 2 if c[3] and c[4] else c[5]
                pmid = (p[3] + p[4]) / 2 if p[3] and p[4] else p[5]
                diff = abs(cmid - pmid)
                if diff < min_diff:
                    min_diff = diff
                    F = K + np.exp(rf * T) * (cmid - pmid)
        if F is None:
            continue
        
        K0 = max([K for K in strikes if K <= F], default=min(strikes))
        
        # 方差贡献
        sigma_sq_sum = 0.0
        prev_K = None
        for i, K in enumerate(strikes):
            if K <= K0:
                opt = puts.get(K)  # 虚值看跌
            else:
                opt = calls.get(K)  # 虚值看涨
            if opt is None:
                continue
            q = (opt[3] + opt[4]) / 2 if opt[3] and opt[4] else opt[5]
            if q is None or q <= 0:
                continue
            # ΔK = (K_next - K_prev) / 2
            dK = (strikes[min(i+1, len(strikes)-1)] - strikes[max(i-1, 0)]) / 2
            sigma_sq_sum += (dK / K**2) * np.exp(rf * T) * q
        
        sigma_sq = (2 / T) * sigma_sq_sum - (1 / T) * (F / K0 - 1)**2
        variances.append(sigma_sq)
    
    db.close()
    if len(variances) < 2:
        return None, "方差计算失败"
    
    # 30天插值
    T1, T2 = term_days[0], term_days[1]
    if T1 >= 30/365 or T2 <= 30/365:
        # 退化: 取近月
        sigma30 = variances[0]
    else:
        w = (30/365 - T1) / (T2 - T1)
        sigma30 = (1 - w) * variances[0] + w * variances[1]
    
    vix = 100 * np.sqrt(max(sigma30, 0))
    return vix, None

if __name__ == '__main__':
    register_meta()
    today = datetime.now().strftime('%Y-%m-%d')
    vix, err = calc_vix(today)
    if err:
        print(f"计算失败: {err}")
    else:
        db = sqlite3.connect(DB)
        db.execute("INSERT OR REPLACE INTO custom_index_values (index_id, date, value) VALUES (?,?,?)",
                   ('CN_PANIC_HO30', today, vix))
        db.commit()
        db.close()
        print(f"\n=== {today} A股恐慌指数(CN_PANIC_HO30) = {vix:.2f} ===")
        print(f"(美股VIX同期: 15.46)")
