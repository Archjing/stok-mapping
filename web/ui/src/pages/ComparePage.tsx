import { useEffect, useMemo, useState } from 'react';
import { SearchSymbolBox } from '../components/SearchSymbolBox';
import { CandleChartView } from '../components/CandleChartView';
import { fetchCandles, type CandleData } from '../api/research';
import { useTheme } from '../components/ThemeContext';

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

type Mode = 'line' | 'candle';

/** 任意两标的对比：折线（原站 SVG）或蜡烛（ECharts 双 K 线）。 */
export function ComparePage() {
  const [symbols, setSymbols] = useState<Record<string, SymbolInfo[]>>({ us_daily_bars: [], etf_qfq: [] });
  const [loading, setLoading] = useState(true);
  const [sourceStorage, setSourceStorage] = useState('us_daily_bars');
  const [source, setSource] = useState('^SOX');
  const [targetStorage, setTargetStorage] = useState('etf_qfq');
  const [target, setTarget] = useState('SH.512480');
  const [start, setStart] = useState('2025-01-01');
  const [end, setEnd] = useState('');
  const [mode, setMode] = useState<Mode>('line');
  const [lineUrl, setLineUrl] = useState('');
  const [candleData, setCandleData] = useState<CandleData | null>(null);
  const [candleLoading, setCandleLoading] = useState(false);
  const [note, setNote] = useState('');
  const theme = useTheme();

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

  const params = () => new URLSearchParams({ source, source_storage: sourceStorage, target, target_storage: targetStorage, start }).toString();

  const build = () => {
    if (!source || !target) {
      setNote('请先选择源标的与目标标的。');
      return;
    }
    if (start && end && end < start) {
      setNote('结束日期不能早于起始日期。');
      return;
    }
    setNote('');
    const base = params();
    if (mode === 'line') {
      setCandleData(null);
      const p = new URLSearchParams(base);
      if (end) p.set('end', end);
      p.set('title', `${source} 与 ${target} 对照图`);
      setLineUrl(`/api/research/comparison/explore?${p.toString()}`);
    } else {
      setLineUrl('');
      setCandleLoading(true);
      const p = new URLSearchParams(base);
      if (end) p.set('end', end);
      fetchCandles({ source, source_storage: sourceStorage, target, target_storage: targetStorage, start, end })
        .then((d) => setCandleData(d))
        .catch((e) => setNote(`蜡烛图加载失败：${e}`))
        .finally(() => setCandleLoading(false));
    }
  };

  const applyPreset = (p: (typeof PRESETS)[number]) => {
    setSourceStorage(p.source_storage);
    setSource(p.source);
    setTargetStorage(p.target_storage);
    setTarget(p.target);
  };

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
        <div className="explore-field">
          <span className="lbl">源标的</span>
          <select className="explore-select" value={sourceStorage} onChange={(e) => { setSourceStorage(e.target.value); setSource(''); }}>
            {Object.entries(STORAGE_LABELS).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </select>
          <SearchSymbolBox options={sourceList} value={source} onSelect={(s) => setSource(s.symbol)} />
        </div>
        <div className="explore-field">
          <span className="lbl">目标</span>
          <select className="explore-select" value={targetStorage} onChange={(e) => { setTargetStorage(e.target.value); setTarget(''); }}>
            {Object.entries(STORAGE_LABELS).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </select>
          <SearchSymbolBox options={targetList} value={target} onSelect={(s) => setTarget(s.symbol)} />
        </div>
        <div className="explore-field">
          <span className="lbl">起止</span>
          <input className="explore-input" type="date" value={start} onChange={(e) => setStart(e.target.value)} />
          <span className="explore-dash">–</span>
          <input className="explore-input" type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
        </div>
        <div className="seg">
          <button className={mode === 'line' ? 'active' : ''} onClick={() => setMode('line')}>
            折线
          </button>
          <button className={mode === 'candle' ? 'active' : ''} onClick={() => setMode('candle')}>
            蜡烛
          </button>
        </div>
        <button className="explore-btn" onClick={build} disabled={loading}>
          {loading ? '加载标的……' : '生成对照图'}
        </button>
      </div>
      {note && <p className="notice-text">{note}</p>}
      {mode === 'line' && lineUrl && (
        <>
          <div className="explore-result-head">
            <h3 className="section-title">{source} 与 {target} 对照图</h3>
            <button className="explore-chip" onClick={() => { navigator.clipboard?.writeText(window.location.origin + lineUrl); setNote('链接已复制。'); }}>
              复制链接
            </button>
          </div>
          <iframe title={`${source} 与 ${target}`} src={lineUrl} style={{ width: '100%', height: 560, border: '1px solid var(--ui-hairline)' }} />
        </>
      )}
      {mode === 'candle' && candleData && <CandleChartView data={candleData} theme={theme} />}
      {mode === 'candle' && candleLoading && !candleData && <p className="dim-text">载入蜡烛图……</p>}
    </div>
  );
}
