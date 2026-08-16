import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useECharts } from '../chart/useECharts';
import { pal } from '../chart/theme';
import type { Theme } from '../chart/theme';
import {
  buildDashOption,
  dashZoomRange,
  makeDashCtrl,
  rebuildDashSeries,
  type DashCtrl,
  type DashRangeKey,
} from '../chart/dashboardChart';
import { fetchBars, type Bar, type SearchHit } from '../api/market';
import { CORE_INDICES, coreIndexName } from '../lib/instruments';
import {
  MA_SPANS,
  NORM_LABEL,
  colorMapForSymbols,
  type DashMode,
  type MaSpan,
  type Normalization,
  type DashInstrument,
} from '../lib/dashboard';
import { SearchBox } from './SearchBox';

const NORMS: Normalization[] = ['window', 'first', 'vol', 'zscore'];

/** 每种归一化的通俗说明（面板下方，随选择显示对应一条）。 */
const NORM_HELP: Record<Normalization, string> = {
  window: '以可见窗口首日收盘为 100，纵轴即相对窗口起点的涨跌幅（%），看同期谁涨得多。',
  first: '以各自上市首日收盘为 100，纵轴即上市以来涨跌幅（%），看长期各自涨幅。',
  vol: '用「涨跌幅 ÷ 平时波动幅度」画线。波动大的股票同样的涨幅会被压小、波动小的会被放大，所以线越陡 = 单位波动赚得越多 = 趋势越实在。',
  zscore: '纵轴 0=窗口均值，±1=一个标准差，看相对自身历史所处的位置。',
};
const MODES: Array<{ key: DashMode; label: string }> = [
  { key: 'candle', label: '蜡烛' },
  { key: 'close', label: '收盘' },
  { key: 'ma', label: '均线' },
];
const RANGES: Array<{ key: DashRangeKey; label: string }> = [
  { key: 'all', label: '全部' },
  { key: '5y', label: '5年' },
  { key: '3y', label: '3年' },
  { key: '1y', label: '1年' },
];

interface Props {
  theme: Theme;
}

export function ComparisonDashboard({ theme }: Props) {
  const { ref, chart } = useECharts();
  const [selected, setSelected] = useState<Set<string>>(
    () => new Set(['SH.000001', 'SZ.399001', 'SZ.399006']),
  );
  // 「池成员」与「是否显示线」分离：点击 chip 只切换 enabled（列表不清除），× 才从池移除
  const [enabled, setEnabled] = useState<Set<string>>(
    () => new Set(['SH.000001', 'SZ.399001', 'SZ.399006']),
  );
  const [stockMeta, setStockMeta] = useState<Record<string, { name: string }>>({});
  const [barsMap, setBarsMap] = useState<Record<string, Bar[]>>({});
  const [mode, setMode] = useState<DashMode>('close');
  const [maSpan, setMaSpan] = useState<MaSpan>(20);
  const [norm, setNorm] = useState<Normalization>('window');

  // 同池去重后的稳定取色（chips 与图线共用，保证一致且池内不撞色）
  const colorMap = useMemo(() => colorMapForSymbols(selected), [selected]);

  const ctrlRef = useRef<DashCtrl | null>(null);
  const colorsRef = useRef<Map<string, string>>(new Map());
  const themeRef = useRef(theme);
  const modeRef = useRef(mode);
  const maSpanRef = useRef(maSpan);
  const normRef = useRef(norm);
  const [, setTick] = useState(0);

  modeRef.current = mode;
  maSpanRef.current = maSpan;
  normRef.current = norm;
  themeRef.current = theme;

  const nameOf = useCallback(
    (s: string) => coreIndexName(s) ?? stockMeta[s]?.name ?? s,
    [stockMeta],
  );

  // 拉取选中标的 bars：近一年先行，再补全量
  useEffect(() => {
    let alive = true;
    for (const s of selected) {
      if (barsMap[s] && barsMap[s].length > 0) continue;
      (async () => {
        try {
          const recent = await fetchBars(s, { recent: '1y' });
          if (!alive) return;
          setBarsMap((m) => ({ ...m, [s]: recent }));
          const full = await fetchBars(s);
          if (!alive) return;
          setBarsMap((m) => ({ ...m, [s]: full }));
        } catch {
          /* ignore */
        }
      })();
    }
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected]);

  // 重建图表
  useEffect(() => {
    const c = chart();
    if (!c) return;
    const insts: DashInstrument[] = [...selected]
      .filter((s) => enabled.has(s))
      .map((s) => ({ symbol: s, name: nameOf(s), bars: barsMap[s] ?? [] }))
      .filter((i) => i.bars.length > 0);
    if (insts.length === 0) {
      c.setOption(
        {
          backgroundColor: pal(themeRef.current).bg,
          grid: { left: 72, right: 24, top: 20, bottom: 74 },
          xAxis: { type: 'category', data: [] },
          yAxis: { scale: true },
          series: [],
        },
        { notMerge: true },
      );
      ctrlRef.current = null;
      return;
    }
    const ctrl = makeDashCtrl(insts);
    ctrl.mode = modeRef.current;
    ctrl.maSpan = maSpanRef.current;
    ctrl.norm = normRef.current;
    if (ctrlRef.current) ctrl.zoom = ctrlRef.current.zoom;
    ctrlRef.current = ctrl;
    colorsRef.current = colorMap;

    c.setOption(buildDashOption(ctrl, pal(themeRef.current), colorsRef.current), { notMerge: true });
    c.off('datazoom');
    c.off('dblclick');
    c.on('datazoom', () => {
      const cc = ctrlRef.current;
      if (!cc || cc.programmatic) return;
      const opt = c.getOption() as { dataZoom?: Array<{ start?: number; end?: number }> };
      const dz = opt.dataZoom;
      if (dz && dz.length) cc.zoom = { start: dz[0].start ?? 0, end: dz[0].end ?? 100 };
      window.setTimeout(() => {
        const cc2 = ctrlRef.current;
        if (cc2) rebuildDashSeries(c, cc2, colorsRef.current);
      }, 80);
    });
    c.on('dblclick', () => {
      const cc = ctrlRef.current;
      if (cc) dashZoomRange(c, cc, 'all', colorsRef.current);
    });
    setTick((n) => n + 1);
  }, [selected, enabled, barsMap, mode, maSpan, norm, theme, nameOf, chart]);

  const addStock = useCallback((hit: SearchHit) => {
    setStockMeta((m) => ({ ...m, [hit.symbol]: { name: hit.name } }));
    setSelected((s) => {
      const n = new Set(s);
      n.add(hit.symbol);
      return n;
    });
    setEnabled((e) => {
      const n = new Set(e);
      n.add(hit.symbol);
      return n;
    });
  }, []);

  // 指数 chip：仅切换显示状态（指数始终在池中）
  const toggleIndex = useCallback((symbol: string) => {
    setEnabled((e) => {
      const n = new Set(e);
      if (n.has(symbol)) n.delete(symbol);
      else n.add(symbol);
      return n;
    });
  }, []);

  // 个股 chip：点击同样只切换显示状态
  const toggleStock = useCallback((symbol: string) => {
    setEnabled((e) => {
      const n = new Set(e);
      if (n.has(symbol)) n.delete(symbol);
      else n.add(symbol);
      return n;
    });
  }, []);

  const removeStock = useCallback((symbol: string) => {
    setSelected((s) => {
      const n = new Set(s);
      n.delete(symbol);
      return n;
    });
    setEnabled((e) => {
      const n = new Set(e);
      n.delete(symbol);
      return n;
    });
  }, []);

  const onRange = useCallback(
    (key: DashRangeKey) => {
      const c = chart();
      const cc = ctrlRef.current;
      if (c && cc) dashZoomRange(c, cc, key, colorsRef.current);
      setTick((n) => n + 1);
    },
    [chart],
  );

  return (
    <div className="dash">
      <section className="controls">
        {/* 从左至右：标的标签 → 搜索框 → 对照池 chips */}
        <div className="ctrl ctrl-wide">
          <span className="lbl">标的</span>
          <SearchBox onSelect={addStock} />
          <div className="checks chips-row">
            {CORE_INDICES.map((i) => (
              <label key={i.symbol} className={`chip${enabled.has(i.symbol) ? ' on' : ''}`}>
                <span className="dot" style={{ background: colorMap.get(i.symbol) }} />
                <input
                  type="checkbox"
                  checked={enabled.has(i.symbol)}
                  onChange={() => toggleIndex(i.symbol)}
                />
                <span>{i.name}</span>
              </label>
            ))}
            {[...selected]
              .filter((s) => !coreIndexName(s))
              .map((s) => (
                <span
                  key={s}
                  className={`chip${enabled.has(s) ? ' on' : ''}`}
                  onClick={() => toggleStock(s)}
                  title={enabled.has(s) ? '点击隐藏该线' : '点击显示该线'}
                >
                  <span className="dot" style={{ background: colorMap.get(s) }} />
                  <span>{nameOf(s)}</span>
                  <button
                    className="chip-x"
                    title="从对照池移除"
                    onClick={(e) => {
                      e.stopPropagation();
                      removeStock(s);
                    }}
                  >
                    ×
                  </button>
                </span>
              ))}
          </div>
        </div>
        <div className="ctrl">
          <span className="lbl">对比</span>
          <div className="seg">
            {MODES.map((m) => (
              <button
                key={m.key}
                className={m.key === mode ? 'active' : ''}
                onClick={() => setMode(m.key)}
              >
                {m.label}
              </button>
            ))}
          </div>
          {mode === 'ma' && (
            <div className="seg">
              {MA_SPANS.map((s) => (
                <button
                  key={s}
                  className={s === maSpan ? 'active' : ''}
                  onClick={() => setMaSpan(s)}
                >
                  MA{s}
                </button>
              ))}
            </div>
          )}
        </div>
        <div className="ctrl">
          <span className="lbl">区间</span>
          <div className="seg">
            {RANGES.map((r) => (
              <button key={r.key} onClick={() => onRange(r.key)}>
                {r.label}
              </button>
            ))}
          </div>
        </div>
      </section>

      <div className="chart-wrap">
        <div className="chart-box" ref={ref} />
        <aside className="norm-panel">
          <div className="norm-title">归一化</div>
          <div className="norm-list">
            {NORMS.map((n) => (
              <label key={n} className={n === norm ? 'on' : ''}>
                <input
                  type="radio"
                  name="norm"
                  checked={n === norm}
                  onChange={() => setNorm(n)}
                />
                <span>{NORM_LABEL[n]}</span>
              </label>
            ))}
          </div>
          <div className="norm-help">{NORM_HELP[norm]}</div>
        </aside>
      </div>

      <div className="status">
        对照看板 · {selected.size} 个标的 · 归一化 {NORM_LABEL[norm]} · 滚轮缩放 / 拖拽平移 / 双击复位
      </div>
    </div>
  );
}
