/**
 * 对照看板：多标的（指数 + 个股）在同一时间轴上的归一化对比。
 *
 * 归一化统一为「每标的独立的仿射变换」norm(x) = a·x + b（a>0）：
 * - 仿射保持 OHLC 结构，因此蜡烛/收盘/均线三种对比方式都适用
 * - MA(a·c+b) = a·MA(c)+b 严格成立，均线语义与收盘一致
 *
 * 四种归一化口径（computeNormTransforms）：
 * - window 窗口起点=100：a = 100/base（base=可见窗口起点收盘）
 * - first  首日=100：    a = 100/首日收盘（各自上市首日）
 * - vol    波动率缩放：  a = 100/(base·vol)，b = 100 − 100/vol
 *                        （斜率除以波动率，趋势陡峭度可比）
 * - zscore z 分数：      a = 1/std，b = −mean/std
 *                        （y 轴直接显示 z 值：0=窗口均值，±1=一个标准差）
 */
import type { SeriesOption } from 'echarts';
import type { IndexBar } from './data-types';

export const MA_SPANS = [5, 10, 20, 30, 60] as const;
export type MaSpan = (typeof MA_SPANS)[number];

export type DashMode = 'candle' | 'close' | 'ma';

export type Normalization = 'window' | 'first' | 'vol' | 'zscore';

export const NORM_LABEL: Record<Normalization, string> = {
  window: '窗口起点=100',
  first: '首日=100',
  vol: '波动率缩放',
  zscore: 'z-score',
};

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

export function buildBarMaps(insts: DashInstrument[]): Array<Map<string, IndexBar>> {
  return insts.map((inst) => {
    const map = new Map<string, IndexBar>();
    for (const b of inst.bars) map.set(b.d, b);
    return map;
  });
}

/** 日收益率年化波动率（×√252）。样本不足返回 NaN。 */
export function annualizedVol(closes: number[]): number {
  const n = closes.length;
  if (n < 3) return NaN;
  let sum = 0;
  let sumSq = 0;
  for (let i = 1; i < n; i++) {
    const r = closes[i] / closes[i - 1] - 1;
    sum += r;
    sumSq += r * r;
  }
  const m = sum / (n - 1);
  const variance = Math.max(0, sumSq / (n - 1) - m * m);
  return Math.sqrt(variance) * Math.sqrt(252);
}

export interface NormTransform {
  a: number;
  b: number;
  /** 窗口起点收盘（window/first 模式下即基准） */
  base: number;
  vol: number;
  mean: number;
  std: number;
}

/** 计算每个标的在当前可见窗口下的归一化仿射参数。 */
export function computeNormTransforms(
  insts: DashInstrument[],
  windowStart: string,
  windowEnd: string,
  norm: Normalization,
): NormTransform[] {
  return insts.map((inst) => {
    const firstClose = inst.bars.length > 0 ? inst.bars[0].c : NaN;
    const winBars = inst.bars.filter((b) => b.d >= windowStart && b.d <= windowEnd);
    const base = winBars.length > 0 ? winBars[0].c : NaN;
    const closes = winBars.map((b) => b.c);
    const vol = annualizedVol(closes);
    const mean = closes.length > 0 ? closes.reduce((s, c) => s + c, 0) / closes.length : NaN;
    const std =
      closes.length > 1
        ? Math.sqrt(closes.reduce((s, c) => s + (c - mean) ** 2, 0) / closes.length)
        : NaN;

    let a = NaN;
    let b = 0;
    if (norm === 'window') {
      a = 100 / base;
    } else if (norm === 'first') {
      a = 100 / firstClose;
    } else if (norm === 'vol') {
      a = 100 / (base * vol);
      b = 100 - 100 / vol;
    } else {
      // z-score：y 轴直接显示 z 值（0=均值，±1=一个标准差）
      a = 1 / std;
      b = -mean / std;
    }
    return { a, b, base, vol, mean, std };
  });
}

export interface DashSeriesOpts {
  mode: DashMode;
  maSpan: MaSpan;
  norm: Normalization;
  windowStart: string;
  windowEnd: string;
  /** 按 symbol 稳定的取色表（checkbox / 图线 / 悬浮提示共用） */
  colors: ReadonlyMap<string, string>;
}

export function buildDashSeries(
  insts: DashInstrument[],
  dates: string[],
  opts: DashSeriesOpts,
): SeriesOption[] {
  const transforms = computeNormTransforms(insts, opts.windowStart, opts.windowEnd, opts.norm);

  const out: (SeriesOption | null)[] = insts.map((inst, k) => {
    const t = transforms[k];
    if (!t || !Number.isFinite(t.a) || t.a <= 0) return null;
    const tr = (x: number): number => Number((t.a * x + t.b).toFixed(2));
    const color = opts.colors.get(inst.symbol) ?? '#8a827b';
    const map = new Map<string, IndexBar>();
    for (const b of inst.bars) map.set(b.d, b);

    if (opts.mode === 'ma') {
      const closes = inst.bars.map((b) => b.c);
      const mas = sma(closes, opts.maSpan);
      const idxByDate = new Map<string, number>();
      inst.bars.forEach((b, i) => idxByDate.set(b.d, i));
      const data = dates.map((d) => {
        const i = idxByDate.get(d);
        if (i == null) return null;
        const v = mas[i];
        return v == null ? null : tr(v);
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

    if (opts.mode === 'close') {
      const data = dates.map((d) => {
        const b = map.get(d);
        return b ? tr(b.c) : null;
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

    // candle：同一标的用同一颜色，便于多序列区分；仿射保持 OHLC 结构
    const data = dates.map((d) => {
      const b = map.get(d);
      return b ? [tr(b.o), tr(b.c), tr(b.l), tr(b.h)] : null;
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
  windowStart: string,
  windowEnd: string,
  norm: Normalization,
  colors: ReadonlyMap<string, string>,
  tc: DashTooltipColors,
): string {
  const date = dates[dataIndex];
  const transforms = computeNormTransforms(insts, windowStart, windowEnd, norm);
  const rows: string[] = [
    `<div style="font-weight:600;margin-bottom:4px">${date} · 归一化对照（${NORM_LABEL[norm]}）</div>`,
  ];
  insts.forEach((inst, k) => {
    const t = transforms[k];
    const bar = barMaps[k]?.get(date);
    if (!bar || !t || !Number.isFinite(t.a) || t.a <= 0) return;
    const color = colors.get(inst.symbol) ?? '#8a827b';
    const normVal = t.a * bar.c + t.b;
    let ctx: string;
    if (norm === 'vol') {
      const rv = ((bar.c / t.base - 1) / t.vol) * 100;
      ctx = `回报/波动 ${rv >= 0 ? '+' : ''}${rv.toFixed(1)}`;
    } else if (norm === 'zscore') {
      ctx = `z ${((bar.c - t.mean) / t.std).toFixed(2)}`;
    } else {
      const pct = (bar.c / t.base - 1) * 100;
      const pctColor = pct >= 0 ? tc.up : tc.down;
      ctx = `<span style="color:${pctColor}">${pct >= 0 ? '+' : ''}${pct.toFixed(1)}%</span>`;
    }
    rows.push(
      `<div style="white-space:nowrap"><span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:${color};margin-right:5px"></span>${inst.name} <b>${normVal.toFixed(1)}</b> ${ctx} <span style="color:${tc.dim}">(收 ${bar.c.toFixed(2)})</span></div>`,
    );
  });
  return rows.join('');
}
