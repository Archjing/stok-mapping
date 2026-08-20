import { useCallback, useEffect, useRef, useState } from 'react';
import { useECharts } from '../chart/useECharts';
import { SearchBox } from './SearchBox';
import {
  aggregate,
  handleZoomChange,
  initView,
  rebuildTheme,
  setEnabledMAs,
  zoomRange,
  type KLineCtrl,
  type RangeKey,
} from '../chart/kline';
import { pal } from '../chart/theme';
import type { Theme } from '../chart/theme';
import { MA_SPANS, type MaSpan } from '../lib/dashboard';
import { TF_LABEL } from '../lib/aggregate';
import type { IndexBar } from '../lib/data-types';
import type { Market } from '../api/market';

interface Props {
  symbol: string;
  name: string;
  bars: IndexBar[];
  theme: Theme;
  indices: ReadonlyArray<{ symbol: string; name: string }>;
  market: Market;
  onSelectSymbol: (symbol: string, name?: string) => void;
}

const RANGES: Array<{ key: RangeKey; label: string }> = [
  { key: 'all', label: '全部' },
  { key: '5y', label: '5年' },
  { key: '3y', label: '3年' },
  { key: '1y', label: '1年' },
];

export function KLineChart({ symbol, name, bars, theme, indices, market, onSelectSymbol }: Props) {
  const { ref, chart } = useECharts();
  const ctrlRef = useRef<KLineCtrl>({
    daily: bars,
    agg: aggregate(bars, '1D'),
    enabledMAs: new Set<MaSpan>([5, 10, 20, 60]),
    activeRange: '1y',
    programmatic: false,
  });
  const nameRef = useRef(name);
  const themeRef = useRef(theme);
  const [, setTick] = useState(0);

  // 数据/代码变化 → 重置视图
  useEffect(() => {
    if (bars.length === 0) return;
    nameRef.current = name;
    ctrlRef.current = {
      daily: bars,
      agg: aggregate(bars, '1D'),
      enabledMAs: new Set<MaSpan>([5, 10, 20, 60]),
      activeRange: '1y',
      programmatic: false,
    };
    const c = chart();
    if (!c) return;
    initView(c, ctrlRef.current, name, pal(themeRef.current));
    c.off('datazoom');
    c.off('dblclick');
    c.on('datazoom', () => {
      const ctrl = ctrlRef.current;
      if (ctrl.programmatic) return;
      ctrl.activeRange = 'custom';
      handleZoomChange(c, ctrl, nameRef.current, pal(themeRef.current));
      setTick((n) => n + 1);
    });
    c.on('dblclick', () => {
      const ctrl = ctrlRef.current;
      zoomRange(c, ctrl, 'all', nameRef.current, pal(themeRef.current));
      setTick((n) => n + 1);
    });
    setTick((n) => n + 1);
  }, [symbol, bars, chart]);

  // 主题切换 → 保留缩放重建
  useEffect(() => {
    themeRef.current = theme;
    const c = chart();
    const ctrl = ctrlRef.current;
    if (c && ctrl.daily.length > 0) rebuildTheme(c, ctrl, nameRef.current, pal(theme));
    setTick((n) => n + 1);
  }, [theme, chart]);

  const toggleMa = useCallback(
    (span: MaSpan, checked: boolean) => {
      const ctrl = ctrlRef.current;
      const next = new Set(ctrl.enabledMAs);
      if (checked) next.add(span);
      else next.delete(span);
      const c = chart();
      if (c) setEnabledMAs(c, ctrl, next, nameRef.current, pal(themeRef.current));
      setTick((n) => n + 1);
    },
    [chart],
  );

  const onRange = useCallback(
    (key: RangeKey) => {
      const c = chart();
      if (!c) return;
      const ctrl = ctrlRef.current;
      zoomRange(c, ctrl, key, nameRef.current, pal(themeRef.current));
      setTick((n) => n + 1);
    },
    [chart],
  );

  const ctrl = ctrlRef.current;
  const last = ctrl.daily[ctrl.daily.length - 1];
  const prev = ctrl.daily[ctrl.daily.length - 2];
  const chg = prev && last ? ((last.c - prev.c) / prev.c) * 100 : null;
  const p = pal(theme);
  const chgColor = chg == null ? p.dim : chg >= 0 ? p.up : p.down;
  const maLast = ctrl.agg.ma['5'].length - 1;

  return (
    <div className="kline">
      <div className="readout">
        <span className="tf-badge">{TF_LABEL[ctrl.agg.tf]}</span>
        <span className="r-name">{name}<span className="r-code">{symbol}</span></span>
        <span className="r-price" style={{ color: chgColor }}>{last?.c.toFixed(2)}</span>
        <span className="r-chg" style={{ color: chgColor }}>
          {chg == null ? '—' : `${chg >= 0 ? '+' : ''}${chg.toFixed(2)}%`}
        </span>
        <span className="r-ma">
          {MA_SPANS.filter((s) => ctrl.enabledMAs.has(s)).map((s) => {
            const v = ctrl.agg.ma[s][maLast];
            return v == null ? null : (
              <span key={s} style={{ color: p.ma[s] }}>MA{s} {v.toFixed(2)}</span>
            );
          })}
        </span>
      </div>

      <div className="controls">
        <div className="ctrl">
          <span className="lbl">指数</span>
          {indices.map((i) => (
            <button
              key={i.symbol}
              className={i.symbol === symbol ? 'active' : ''}
              onClick={() => onSelectSymbol(i.symbol, i.name)}
            >
              {i.name}
            </button>
          ))}
          <SearchBox market={market} onSelect={(hit) => onSelectSymbol(hit.symbol, hit.name)} />
        </div>
        <div className="ctrl">
          <span className="lbl">均线</span>
          {MA_SPANS.map((s) => (
            <label key={s} className={`chip${ctrl.enabledMAs.has(s) ? ' on' : ''}`}>
              <span className="dot" style={{ background: p.ma[s] }} />
              <input
                type="checkbox"
                checked={ctrl.enabledMAs.has(s)}
                onChange={(e) => toggleMa(s, e.target.checked)}
              />
              <span>MA{s}</span>
            </label>
          ))}
        </div>
        <div className="ctrl">
          <span className="lbl">区间</span>
          {RANGES.map((r) => (
            <button
              key={r.key}
              className={ctrl.activeRange === r.key ? 'active' : ''}
              onClick={() => onRange(r.key)}
            >
              {r.label}
            </button>
          ))}
        </div>
      </div>

      <div className="chart-box" ref={ref} />
    </div>
  );
}
