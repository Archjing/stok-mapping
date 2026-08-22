import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { fetchAccountCharts, type AccountChartItem } from '../api/research';
import { ComparisonChartView } from '../components/ComparisonChartView';
import { StrategyExplain } from '../components/StrategyExplain';
import { useTheme } from '../components/ThemeContext';

/** 账户跨市场映射对照图（原静态站 accounts/<slug>/research/<chart-slug>/）。 */
export function AccountChartsPage() {
  const { accountId = '' } = useParams();
  const [charts, setCharts] = useState<AccountChartItem[]>([]);
  const [error, setError] = useState('');
  const theme = useTheme();

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
      {charts.map((item) =>
        item.data ? (
          <ComparisonChartView key={item.slug} data={item.data} theme={theme} />
        ) : (
          <p key={item.slug} className="dim-text">
            {item.button_label}：数据不足
          </p>
        ),
      )}
      <StrategyExplain accountId={accountId} />
    </div>
  );
}
