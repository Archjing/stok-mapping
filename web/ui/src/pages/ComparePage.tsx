import { useEffect, useMemo, useState } from 'react';

const STORAGE_LABELS: Record<string, string> = {
  us_daily_bars: '美股日线',
  etf_qfq: 'ETF 前复权',
};

interface SymbolInfo {
  symbol: string;
  label: string;
}

/** 常用对比组合（用户已验证的研究映射，一键加载）。 */
const PRESETS: { name: string; source: string; source_storage: string; target: string; target_storage: string }[] = [
  { name: '^SOX → 半导体ETF 512480', source: '^SOX', source_storage: 'us_daily_bars', target: 'SH.512480', target_storage: 'etf_qfq' },
  { name: '^VIX → 半导体ETF 512480', source: '^VIX', source_storage: 'us_daily_bars', target: 'SH.512480', target_storage: 'etf_qfq' },
  { name: '^SOX → 科创芯片ETF 588200', source: '^SOX', source_storage: 'us_daily_bars', target: 'SH.588200', target_storage: 'etf_qfq' },
];

/** 任意两标的对比：选源/目标（storage + symbol）→ 声明式生成原站同款对照图页。 */
export function ComparePage() {
  const [symbols, setSymbols] = useState<Record<string, SymbolInfo[]>>({ us_daily_bars: [], etf_qfq: [] });
  const [loading, setLoading] = useState(true);
  const [sourceStorage, setSourceStorage] = useState('us_daily_bars');
  const [source, setSource] = useState('^SOX');
  const [targetStorage, setTargetStorage] = useState('etf_qfq');
  const [target, setTarget] = useState('SH.512480');
  const [start, setStart] = useState('2025-01-01');
  const [url, setUrl] = useState('');
  const [note, setNote] = useState('');

  useEffect(() => {
    fetch('/api/research/symbols')
      .then((r) => r.json())
      .then((d) => {
        setSymbols(d);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  const sourceList = useMemo(() => symbols[sourceStorage] ?? [], [symbols, sourceStorage]);
  const targetList = useMemo(() => symbols[targetStorage] ?? [], [symbols, targetStorage]);

  const build = () => {
    if (!source || !target) {
      setNote('请先选择源标的与目标标的。');
      return;
    }
    setNote('');
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

  const applyPreset = (p: (typeof PRESETS)[number]) => {
    setSourceStorage(p.source_storage);
    setSource(p.source);
    setTargetStorage(p.target_storage);
    setTarget(p.target);
  };

  const select = (
    label: string,
    storage: string,
    setStorage: (v: string) => void,
    setSymbol: (v: string) => void,
    symbol: string,
    list: SymbolInfo[],
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
        className="explore-select explore-symbol"
        value={symbol}
        onChange={(e) => setSymbol(e.target.value)}
        disabled={loading || list.length === 0}
      >
        {list.map((s) => (
          <option key={s.symbol} value={s.symbol}>
            {s.symbol} · {s.label}
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
      <div className="explore-presets">
        <span className="lbl">常用组合</span>
        {PRESETS.map((p) => (
          <button key={p.name} className="explore-chip" onClick={() => applyPreset(p)}>
            {p.name}
          </button>
        ))}
      </div>
      <div className="explore-form">
        {select('源标的', sourceStorage, setSourceStorage, setSource, source, sourceList)}
        {select('目标', targetStorage, setTargetStorage, setTarget, target, targetList)}
        <div className="explore-field">
          <span className="lbl">起始日期</span>
          <input className="explore-input" type="date" value={start} onChange={(e) => setStart(e.target.value)} />
        </div>
        <button className="explore-btn" onClick={build} disabled={loading}>
          {loading ? '加载标的……' : '生成对照图'}
        </button>
      </div>
      {note && <p className="notice-text">{note}</p>}
      {url && (
        <>
          <div className="explore-result-head">
            <h3 className="section-title">
              {source} 与 {target} 对照图
            </h3>
            <button
              className="explore-chip"
              onClick={() => {
                navigator.clipboard?.writeText(window.location.origin + url);
                setNote('链接已复制。');
              }}
            >
              复制链接
            </button>
          </div>
          <iframe
            title={`${source} 与 ${target}`}
            src={url}
            style={{ width: '100%', height: 560, border: '1px solid var(--ui-hairline)' }}
          />
        </>
      )}
    </div>
  );
}
