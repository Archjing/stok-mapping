import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { fetchBrief, type BriefData } from '../api/accounts';

/** 每日简报：账户就绪状态 + 汇总表 + 入口（移植自原静态站 brief/index.html）。 */
export function BriefPage() {
  const [data, setData] = useState<BriefData | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    let alive = true;
    fetchBrief()
      .then((d) => alive && setData(d))
      .catch((e) => alive && setError(`简报加载失败：${e}`));
    return () => {
      alive = false;
    };
  }, []);

  return (
    <div className="page-view">
      <div className="view-head">
        <h2 className="view-title">量化每日简报</h2>
      </div>
      {error && <p className="error">{error}</p>}
      {!data && !error && <p className="dim-text">加载中……</p>}
      {data && (
        <>
          <div className="brief-hero">
            <div>
              <p className="brief-kicker">DAILY BRIEF</p>
              <h3 className="brief-title">账户、观察池与证据入口</h3>
              <p className="dim-text">
                汇总当前启用模拟账户的最新确认账单、盘前观察池与完整交易台账入口。页面不直接生成交易信号，也不替代
                strategy-admission 或人工复核。
              </p>
            </div>
            <div className={`brief-status ${data.ready_accounts === data.account_count ? 'ready' : 'warning'}`}>
              {data.ready_accounts === data.account_count
                ? '全部启用账户已有确认账单'
                : '部分账户暂无确认账单，简报只展示可用证据'}
            </div>
          </div>
          <div className="summary-cards">
            <div className="summary-card">
              <span>启用账户</span>
              <strong>{data.account_count}</strong>
            </div>
            <div className="summary-card">
              <span>有确认账单账户</span>
              <strong>{data.ready_accounts}</strong>
            </div>
            <div className="summary-card">
              <span>最新确认账单日</span>
              <strong>{data.latest_bill_date}</strong>
            </div>
            <div className="summary-card">
              <span>简报边界</span>
              <strong>研究辅助</strong>
            </div>
          </div>
          <div className="table-wrap">
            <table className="report-table">
              <thead>
                <tr>
                  <th>账户 ID</th>
                  <th>账户名称</th>
                  <th>最新账单日</th>
                  <th>总资产</th>
                  <th>仓位</th>
                  <th>入口</th>
                </tr>
              </thead>
              <tbody>
                {data.accounts.length === 0 && (
                  <tr>
                    <td colSpan={6}>暂无启用的模拟账户</td>
                  </tr>
                )}
                {data.accounts.map((a) => (
                  <tr key={a.slug}>
                    <td className="mono">{a.account_id}</td>
                    <td>
                      <Link to={`/accounts/${a.slug}`} className="inline-link">
                        {a.name}
                      </Link>
                    </td>
                    <td className="num-center">{a.latest_bill_date || '暂无'}</td>
                    <td className="num-right">{a.total_asset || '暂无'}</td>
                    <td className="num-center">{a.target_exposure || '暂无'}</td>
                    <td>
                      <Link to={`/accounts/${a.slug}/watchlist`} className="inline-link">
                        观察池
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
