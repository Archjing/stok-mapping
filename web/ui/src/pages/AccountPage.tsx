import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { fetchAccount, type AccountMeta } from '../api/accounts';
import { StrategyExplain } from '../components/StrategyExplain';

/** 账户主页：资产摘要卡 + 快捷入口（移植自原静态站 accounts/<slug>/index.html）。 */
export function AccountPage() {
  const { accountId = '' } = useParams();
  const [meta, setMeta] = useState<AccountMeta | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    let alive = true;
    setMeta(null);
    setError('');
    fetchAccount(accountId)
      .then((m) => alive && setMeta(m))
      .catch((e) => alive && setError(`账户加载失败：${e}`));
    return () => {
      alive = false;
    };
  }, [accountId]);

  if (error) return <div className="page-view"><p className="error">{error}</p></div>;
  if (!meta) return <div className="page-view" />;

  return (
    <div className="page-view">
      <div className="view-head">
        <h2 className="view-title">
          {meta.name}
          <span className="view-code">{meta.account_id}</span>
        </h2>
      </div>
      <div className="summary-cards">
        <div className="summary-card">
          <span>最新账单日</span>
          <strong>{meta.latest_bill_date || '暂无'}</strong>
        </div>
        <div className="summary-card">
          <span>总资产（元）</span>
          <strong>{meta.total_asset || '暂无'}</strong>
        </div>
        <div className="summary-card">
          <span>现金资产</span>
          <strong>{meta.cash_asset || '暂无'}</strong>
        </div>
        <div className="summary-card">
          <span>股票资产</span>
          <strong>{meta.stock_asset || '暂无'}</strong>
        </div>
        <div className="summary-card">
          <span>当前仓位</span>
          <strong>{meta.target_exposure || '暂无'}</strong>
        </div>
        <div className="summary-card">
          <span>建仓日</span>
          <strong>{meta.position_start_date || '暂无'}</strong>
        </div>
      </div>
      <StrategyExplain accountId={meta.slug} />
      <section className="bill-section">
        <h3 className="section-title">快捷入口</h3>
        <div className="quick-links">
          <Link to={`/accounts/${meta.slug}/watchlist`} className="quick-card">
            <span>WATCHLIST</span>
            <strong>最新盘前观察池</strong>
          </Link>
          <Link to={`/accounts/${meta.slug}/bill`} className="quick-card">
            <span>BILL</span>
            <strong>最新模拟交易账单</strong>
          </Link>
          <Link to={`/accounts/${meta.slug}/ledger`} className="quick-card">
            <span>LEDGER</span>
            <strong>完整交易台账</strong>
          </Link>
          <Link to={`/accounts/${meta.slug}/charts`} className="quick-card">
            <span>CHARTS</span>
            <strong>跨市场映射对照图</strong>
          </Link>
          <Link to="/accounts" className="quick-card">
            <span>CONSOLE</span>
            <strong>账户总览</strong>
          </Link>
        </div>
      </section>
    </div>
  );
}
