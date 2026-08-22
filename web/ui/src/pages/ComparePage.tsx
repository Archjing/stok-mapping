import { useEffect, useMemo, useState } from 'react';

const STORAGE_LABELS: Record<string, string> = {
  us_daily_bars: '美股日线',
  etf_qfq: 'ETF 前复权',
};

/** 任意两标的对比：选源/目标（storage + symbol）→ 声明式生成原站同款对照图页。 */
export function ComparePage() {
  const [symbols, setSymbols] = useState<Record<string, string[]>>({ us_daily_bars: [], etf_qfq: [] });
  const [sourceStorage, setSourceStorage] = useState('us_daily_bars');
  const [source, setSource] = useState('^SOX');
  const [targetStorage, setTargetStorage] = useState('etf_qfq');
  const [target, setTarget] = useState('SH.512480');
  const [start, setStart] = useState('2025-01-01');
  const [url, setUrl] = useState('');

  useEffect(() => {
    fetch('/api/research/symbols')
      .then((r) => r.json())
      .then(setSymbols)
      .catch(() => {});
  }, []);

  const sourceList = useMemo(() => symbols[sourceStorage] ?? [], [symbols, sourceStorage]);
  const targetList = useMemo(() => symbols[targetStorage] ?? [], [symbols, targetStorage]);

  const build = () => {
    const params = new URLSearchParams({
      source,
      source_storage: sourceStorage,
      target,
      target_storage: targetStorage,
      start,
      title: `${source} 与 ${target} 对照图`,
    });
    setUrl(`/api/research/comparison/explore?${params.toString()}`);
  };

  const select = (
    label: string,
    storage: string,
    setStorage: (v: string) => void,
    setSymbol: (v: string) => void,
    symbol: string,
    list: string[],
  ) => (
    <div className="explore-field">
      <span className="lbl">{label}</span>
      <select className="explore-select" value={storage} onChange={(e) => setStorage(e.target.value)}>
        {Object.entries(STORAGE_LABELS).map(([k, v]) => (
          <option key={k} value={k}>
            {v}
          </option>
        ))}
      </select>
      <select
        className="explore-select"
        value={symbol}
        onChange={(e) => setSymbol(e.target.value)}
        disabled={list.length === 0}
      >
        {list.map((s) => (
          <option key={s} value={s}>
            {s}
          </option>
        ))}
      </select>
    </div>
  );

  return (
    <div className="page-view">
      <div className="view-head">
        <h2 className="view-title">任意两标的对比</h2>
      </div>
      <div className="explore-form">
        {select('源标的', sourceStorage, setSourceStorage, setSource, source, sourceList)}
        {select('目标', targetStorage, setTargetStorage, setTarget, target, targetList)}
        <div className="explore-field">
          <span className="lbl">起始日期</span>
          <input className="explore-input" type="date" value={start} onChange={(e) => setStart(e.target.value)} />
        </div>
        <button className="explore-btn" onClick={build}>
          生成对照图
        </button>
      </div>
      {url && (
        <iframe
          title={`${source} 与 ${target}`}
          src={url}
          style={{ width: '100%', height: 560, border: '1px solid var(--ui-hairline)' }}
        />
      )}
    </div>
  );
}
