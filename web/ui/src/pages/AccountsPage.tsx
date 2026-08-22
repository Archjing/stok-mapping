import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { fetchAccounts, type AccountMeta } from '../api/accounts';

/** 账户总览：模拟账户列表（移植自原静态站 index.html 账户总览表）。 */
export function AccountsPage() {
  const [accounts, setAccounts] = useState<AccountMeta[]>([]);
  const [error, setError] = useState('');

  useEffect(() => {
    let alive = true;
    fetchAccounts()
      .then((d) => alive && setAccounts(d.accounts))
      .catch((e) => alive && setError(`账户加载失败：${e}`));
    return () => {
      alive = false;
    };
  }, []);

  return (
    <div className="page-view">
      <div className="view-head">
        <h2 className="view-title">模拟账户总览</h2>
      </div>
      {error && <p className="error">{error}</p>}
      <div className="summary-cards">
        <div className="summary-card">
          <span>启用账户</span>
          <strong>{accounts.length}</strong>
        </div>
        <div className="summary-card">
          <span>有确认账单</span>
          <strong>{accounts.filter((a) => a.latest_bill_date).length}</strong>
        </div>
        <div className="summary-card">
          <span>每日简报</span>
          <strong>
            <Link to="/accounts/brief" className="inline-link">
              进入 →
            </Link>
          </strong>
        </div>
      </div>
      <div className="table-wrap">
        <table className="report-table">
          <thead>
            <tr>
              <th>账户 ID</th>
              <th>账户名称</th>
              <th>最新账单日</th>
              <th>建仓日</th>
              <th>总资产</th>
              <th>仓位</th>
              <th>入口</th>
            </tr>
          </thead>
          <tbody>
            {accounts.length === 0 && !error && (
              <tr>
                <td colSpan={7}>暂无启用的模拟账户</td>
              </tr>
            )}
            {accounts.map((a) => (
              <tr key={a.slug}>
                <td className="mono">{a.account_id}</td>
                <td>
                  <Link to={`/accounts/${a.slug}`} className="inline-link">
                    {a.name}
                  </Link>
                </td>
                <td className="num-center">{a.latest_bill_date || '暂无'}</td>
                <td className="num-center">{a.position_start_date || '暂无'}</td>
                <td className="num-right">{a.total_asset || '暂无'}</td>
                <td className="num-center">{a.target_exposure || '暂无'}</td>
                <td>
                  <Link to={`/accounts/${a.slug}`} className="inline-link">
                    账户
                  </Link>{' '}
                  ｜{' '}
                  <Link to={`/accounts/${a.slug}/watchlist`} className="inline-link">
                    观察池
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="notice-text">本页为模拟账户只读快照，口径与 CLI 静态站一致；不生成交易信号，不替代人工复核。</p>
    </div>
  );
}
