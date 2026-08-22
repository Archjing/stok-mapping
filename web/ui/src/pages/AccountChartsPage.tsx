import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { fetchAccountCharts, type AccountChartItem } from '../api/research';
import { StrategyExplain } from '../components/StrategyExplain';

/** 账户跨市场映射对照图：iframe 嵌入原站同款研究页（原静态站 accounts/<slug>/research/）。 */
export function AccountChartsPage() {
  const { accountId = '' } = useParams();
  const [charts, setCharts] = useState<AccountChartItem[]>([]);
  const [error, setError] = useState('');

  useEffect(() => {
    let alive = true;
    setError('');
    fetchAccountCharts(accountId)
      .then((d) => alive && setCharts(d.charts))
      .catch((e) => alive && setError(`映射图加载失败：${e}`));
    return () => {
      alive = false;
    };
  }, [accountId]);

  return (
    <div className="page-view">
      <div className="view-head">
        <h2 className="view-title">跨市场映射对照图</h2>
      </div>
      {error && <p className="error">{error}</p>}
      {!error && charts.length === 0 && <p className="dim-text">该账户暂无映射图。</p>}
      {charts.map((item) => (
        <iframe
          key={item.slug}
          title={item.title}
          src={`/api/accounts/${accountId}/chart-page/${item.slug}`}
          style={{
            width: '100%',
            height: 560,
            border: '1px solid var(--ui-hairline)',
            background: 'transparent',
            marginBottom: 14,
          }}
        />
      ))}
      <StrategyExplain accountId={accountId} />
    </div>
  );
}
