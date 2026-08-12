import sqlite3, os, sys
sys.path.insert(0, "/Users/aj/workspace/stok-mapping")
import akshare as ak
import pandas as pd
from datetime import datetime

DB = os.path.expanduser("~/workspace/stok-mapping/data/custom_indices.sqlite")

def pull_ho_chain(month):
    """拉上证50股指期权(HO)某月合约链, month 形如 'ho2609'"""
    try:
        df = ak.option_cffex_sz50_spot_sina(symbol=month)
        if df is None or len(df) == 0:
            return None
        m_num = month.replace('ho','')
        
        rows = []
        for _, r in df.iterrows():
            strike = float(r['行权价'])
            # 看涨
            rows.append(('CFFEX', 'HO', f'HO{m_num}C{int(strike)}', 'C', strike, m_num,
                         float(r['看涨合约-最新价']), float(r['看涨合约-买价']),
                         float(r['看涨合约-卖价']), float(r['看涨合约-买量']),
                         float(r['看涨合约-持仓量'])))
            # 看跌
            rows.append(('CFFEX', 'HO', f'HO{m_num}P{int(strike)}', 'P', strike, m_num,
                         float(r['看跌合约-最新价']), float(r['看跌合约-买价']),
                         float(r['看跌合约-卖价']), float(r['看跌合约-买量']),
                         float(r['看跌合约-持仓量'])))
        return rows
    except Exception as e:
        print(f'  HO{month} 拉取失败: {str(e)[:80]}')
        return None

def main():
    db = sqlite3.connect(DB)
    today = datetime.now().strftime('%Y-%m-%d')
    
    # 可用月份
    try:
        months = ak.option_cffex_sz50_list_sina()
        if isinstance(months, dict):
            months = sorted(months.get('上证50指数', []))
        print(f'可用月份: {months}')
    except Exception as e:
        print(f'月份列表失败: {e}')
        return
    
    # 拉近月 + 次月
    total = 0
    for month in months[:2]:
        print(f'拉取 HO{month}...')
        rows = pull_ho_chain(month)
        if rows:
            # 清当日旧数据
            db.execute("DELETE FROM option_chains WHERE trade_date=? AND underlying='HO' AND expiry_month=?", 
                       (today, month))
            for row in rows:
                db.execute("""
                    INSERT OR REPLACE INTO option_chains
                    (trade_date, market, underlying, contract, option_type, strike, expiry_month,
                     last_price, bid, ask, volume, open_interest, source)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (today, row[0], row[1], row[2], row[3], row[4], row[5],
                      row[6], row[7], row[8], row[9], row[10], 'akshare_sina'))
            db.commit()
            print(f'  HO{month}: {len(rows)} 条写入')
            total += len(rows)
    
    # 50ETF 现货价
    try:
        spot = ak.option_sse_underlying_spot_price_sina(symbol='sh510050')
        print(f'510050 现货: {spot}')
    except Exception as e:
        print(f'现货价失败: {str(e)[:60]}')
    
    # 无风险利率 (Shibor 3M)
    try:
        shibor = ak.rate_interbank(market='上海银行同业拆借市场', symbol='Shibor人民币', indicator='3月')
        if shibor is not None and len(shibor) > 0:
            latest = shibor.iloc[-1]
            rate = float(latest['利率'])
            db.execute("INSERT OR REPLACE INTO risk_free_rates (date, rate_3m, source) VALUES (?,?,?)",
                       (today, rate, 'akshare_shibor'))
            db.commit()
            print(f'Shibor 3M: {rate}%')
    except Exception as e:
        print(f'Shibor 失败: {str(e)[:60]}')
    
    print(f'\n总计写入 {total} 条期权链')
    print(f"库总量: {db.execute('SELECT COUNT(*) FROM option_chains').fetchone()[0]} 条")
    db.close()

if __name__ == '__main__':
    main()
