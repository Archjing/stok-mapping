import { useEffect, useState } from 'react';
import { fetchComparison, type ComparisonData } from '../api/research';
import { ComparisonChartView } from '../components/ComparisonChartView';
import { useTheme } from '../components/ThemeContext';

/** 研究对照图页（原静态站 research/vix-vs-512480、sox-vs-512480）。 */
export function ResearchComparisonPage({ slug, title }: { slug: string; title: string }) {
  const [data, setData] = useState<ComparisonData | null>(null);
  const [error, setError] = useState('');
  const theme = useTheme();

  useEffect(() => {
    let alive = true;
    setData(null);
    setError('');
    fetchComparison(slug)
      .then((d) => alive && setData(d))
      .catch((e) => alive && setError(`对照图加载失败：${e}`));
    return () => {
      alive = false;
    };
  }, [slug]);

  return (
    <div className="page-view">
      <div className="view-head">
        <h2 className="view-title">{title}</h2>
      </div>
      {error && <p className="error">{error}</p>}
      {!data && !error && <p className="dim-text">加载中……</p>}
      {data && <ComparisonChartView data={data} theme={theme} />}
    </div>
  );
}
