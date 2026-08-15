/**
 * 对照看板：多标的（指数 + 个股）在同一时间轴上的归一化对比。
 *
 * 归一化口径：每个标的以「可见窗口起点」的收盘价为基准 100，
 * 之后所有 OHLC / 收盘 / 均线 都乘以同一比例，从而在同一图底上
 * 比较「谁涨跌更激烈、谁更平缓」。
 */
import type { SeriesOption } from 'echarts';
import type { IndexBar } from './data-types';

export const MA_SPANS = [5, 10, 20, 30, 60] as const;
export type MaSpan = (typeof MA_SPANS)[number];

export type DashMode = 'candle' | 'close' | 'ma';

export interface DashInstrument {
  symbol: string;
  name: string;
  bars: IndexBar[];
}

/** 标的区分色（两种主题下都清晰可辨的中间调）。 */
export const DASH_COLORS = [
  '#d08b30',
  '#426a79',
  '#9a4a8a',
  '#2f8a5f',
  '#b03a3a',
  '#4a6fb0',
  '#8a7a1e',
  '#c95f2e',
  '#5a8a9a',
  '#a05a8a',
  '#3a9a8a',
  '#7a5a2e',
  '#6a4a9a',
  '#b88f55',
];

export function sma(values: number[], period: number): (number | null)[] {
  const out: (number | null)[] = new Array(values.length).fill(null);
  let sum = 0;
  for (let i = 0; i < values.length; i++) {
    sum += values[i];
    if (i >= period) sum -= values[i - period];
    if (i >= period - 1) out[i] = sum / period;
  }
  return out;
}

/** 所有标的自有交易日的并集（排序后），作为共享时间轴。 */
export function buildSharedDates(insts: DashInstrument[]): string[] {
  const set = new Set<string>();
  for (const inst of insts) for (const b of inst.bars) set.add(b.d);
  return [...set].sort();
}

export function dashWindowFromPct(
  dates: string[],
  startPct: number,
  endPct: number,
): { startIdx: number; endIdx: number } {
  const n = dates.length;
  if (n === 0) return { startIdx: 0, endIdx: 0 };
  const startIdx = Math.max(0, Math.min(n - 1, Math.floor((startPct / 100) * (n - 1))));
  const endIdx = Math.max(0, Math.min(n - 1, Math.ceil((endPct / 100) * (n - 1))));
  return { startIdx, endIdx };
}

/** 每个标的在窗口起点的基准收盘价（归一化 base=100；窗口内无数据则为 NaN）。 */
export function computeBaseCloses(insts: DashInstrument[], windowStartDate: string): number[] {
  return insts.map((inst) => {
    const b = inst.bars.find((x) => x.d >= windowStartDate);
    return b ? b.c : NaN;
  });
}

export function buildBarMaps(insts: DashInstrument[]): Array<Map<string, IndexBar>> {
  return insts.map((inst) => {
    const map = new Map<string, IndexBar>();
    for (const b of inst.bars) map.set(b.d, b);
    return map;
  });
}

export interface DashSeriesOpts {
  mode: DashMode;
  maSpan: MaSpan;
  windowStart: string;
  colors: string[];
}

export function buildDashSeries(
  insts: DashInstrument[],
  dates: string[],
  opts: DashSeriesOpts,
): SeriesOption[] {
  const factors = computeBaseCloses(insts, opts.windowStart).map((base) =>
    Number.isFinite(base) && base > 0 ? 100 / base : 0,
  );

  const out: (SeriesOption | null)[] = insts.map((inst, k) => {
    const factor = factors[k];
    if (factor <= 0) return null;
    const color = opts.colors[k % opts.colors.length];

    if (opts.mode === 'ma') {
      const closes = inst.bars.map((b) => b.c);
      const mas = sma(closes, opts.maSpan);
      const idxByDate = new Map<string, number>();
      inst.bars.forEach((b, i) => idxByDate.set(b.d, i));
      const data = dates.map((d) => {
        const i = idxByDate.get(d);
        if (i == null) return null;
        const v = mas[i];
        return v == null ? null : Number((v * factor).toFixed(2));
      });
      return {
        id: `dash-${inst.symbol}`,
        name: inst.name,
        type: 'line',
        data,
        smooth: true,
        showSymbol: false,
        connectNulls: false,
        lineStyle: { width: 1.6, color },
        itemStyle: { color },
        emphasis: { disabled: true },
        z: 3,
      } as SeriesOption;
    }

    const map = new Map<string, IndexBar>();
    for (const b of inst.bars) map.set(b.d, b);

    if (opts.mode === 'close') {
      const data = dates.map((d) => {
        const b = map.get(d);
        return b ? Number((b.c * factor).toFixed(2)) : null;
      });
      return {
        id: `dash-${inst.symbol}`,
        name: inst.name,
        type: 'line',
        data,
        smooth: false,
        showSymbol: false,
        connectNulls: false,
        lineStyle: { width: 1.6, color },
        itemStyle: { color },
        emphasis: { disabled: true },
        z: 3,
      } as SeriesOption;
    }

    // candle：同一标的用同一颜色，便于多序列区分
    const data = dates.map((d) => {
      const b = map.get(d);
      return b
        ? [
            Number((b.o * factor).toFixed(2)),
            Number((b.c * factor).toFixed(2)),
            Number((b.l * factor).toFixed(2)),
            Number((b.h * factor).toFixed(2)),
          ]
        : null;
    });
    return {
      id: `dash-${inst.symbol}`,
      name: inst.name,
      type: 'candlestick',
      data,
      itemStyle: { color, color0: color, borderColor: color, borderColor0: color },
      z: 2,
    } as SeriesOption;
  });

  return out.filter((x): x is SeriesOption => x != null);
}

export interface DashTooltipColors {
  text: string;
  dim: string;
  up: string;
  down: string;
}

export function dashTooltipHtml(
  insts: DashInstrument[],
  barMaps: Array<Map<string, IndexBar>>,
  dates: string[],
  dataIndex: number,
  windowStartDate: string,
  colors: string[],
  tc: DashTooltipColors,
): string {
  const date = dates[dataIndex];
  const bases = computeBaseCloses(insts, windowStartDate);
  const rows: string[] = [
    `<div style="font-weight:600;margin-bottom:4px">${date} · 归一化对照（窗口起点=100）</div>`,
  ];
  insts.forEach((inst, k) => {
    const base = bases[k];
    const bar = barMaps[k]?.get(date);
    if (!bar || !Number.isFinite(base) || base <= 0) return;
    const pct = (bar.c / base - 1) * 100;
    const color = colors[k % colors.length];
    const pctColor = pct >= 0 ? tc.up : tc.down;
    rows.push(
      `<div style="white-space:nowrap"><span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:${color};margin-right:5px"></span>${inst.name} <b>${((bar.c / base) * 100).toFixed(1)}</b> <span style="color:${pctColor}">${pct >= 0 ? '+' : ''}${pct.toFixed(1)}%</span> <span style="color:${tc.dim}">(收 ${bar.c.toFixed(2)})</span></div>`,
    );
  });
  return rows.join('');
}
