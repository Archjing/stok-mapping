import * as echarts from 'echarts/core';
import { CandlestickChart, LineChart } from 'echarts/charts';
import {
  DataZoomComponent,
  GridComponent,
  TooltipComponent,
} from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
import type { EChartsOption, SeriesOption } from 'echarts';

import {
  aggregateDaily,
  tfForDays,
  timeframeForVisibleDays,
  TF_LABEL,
  type Timeframe,
} from './aggregate';
import {
  MA_SPANS,
  DASH_COLORS,
  buildSharedDates,
  dashWindowFromPct,
  buildDashSeries,
  dashTooltipHtml,
  buildBarMaps,
  sma,
  type MaSpan,
  type DashMode,
  type DashInstrument,
} from './dashboard';
import { INDEX_DATA } from './generated/data';
import type { IndexBar, InstrumentMeta } from './data-types';
import './styles.css';

echarts.use([
  CandlestickChart,
  LineChart,
  GridComponent,
  TooltipComponent,
  DataZoomComponent,
  CanvasRenderer,
]);

type Theme = 'dark' | 'light';
type RangeKey = 'all' | '5y' | '3y' | '1y' | 'custom';
type ViewMode = 'single' | 'dash';

interface ThemePalette {
  bg: string;
  panel: string;
  border: string;
  text: string;
  dim: string;
  axisLine: string;
  splitLine: string;
  tooltipBg: string;
  tooltipBorder: string;
  up: string; // 阳线（A股：红涨）
  down: string; // 阴线（A股：绿跌）
  ma: Record<MaSpan, string>;
}

const THEMES: Record<Theme, ThemePalette> = {
  dark: {
    // 原深色系，提升层次对比：画布比页面亮、网格/坐标轴更清晰、弱文本提亮
    bg: '#151d2b',
    panel: '#151d2b',
    border: '#2b3950',
    text: '#eef3fa',
    dim: '#a2b3c8',
    axisLine: '#3a4a66',
    splitLine: '#202b3d',
    tooltipBg: '#1a2434',
    tooltipBorder: '#33415c',
    up: '#ef232a',
    down: '#14b143',
    ma: {
      5: '#f6d365',
      10: '#ff8fab',
      20: '#b388ff',
      30: '#6ee7b7',
      60: '#4fc3f7',
    },
  },
  light: {
    // 原浅色系，提升层次对比：页面底稍深、边框/弱文本加深
    bg: '#ffffff',
    panel: '#ffffff',
    border: '#c9d3df',
    text: '#101827',
    dim: '#56697e',
    axisLine: '#8fa1b8',
    splitLine: '#e6ebf2',
    tooltipBg: '#ffffff',
    tooltipBorder: '#c9d3df',
    up: '#dc2626',
    down: '#16a34a',
    ma: {
      5: '#eab308',
      10: '#ec4899',
      20: '#8b5cf6',
      30: '#10b981',
      60: '#0ea5e9',
    },
  },
};

// DOM 元素在 main()（DOM 就绪后）里再获取：构建产物会把脚本放到 <head>，
// 模块顶层执行时 body 尚未解析，这里取值会得到 null。
let indexSwitchEl: HTMLDivElement;
let maTogglesEl: HTMLDivElement;
let rangeButtonsEl: HTMLDivElement;
let viewSwitchEl: HTMLDivElement;
let controlsSingleEl: HTMLElement;
let controlsDashEl: HTMLElement;
let dashInstrumentsEl: HTMLDivElement;
let dashModeEl: HTMLDivElement;
let dashMaSpanEl: HTMLDivElement;
let dashRangeEl: HTMLDivElement;
let themeToggleEl: HTMLButtonElement;
let readoutEl: HTMLDivElement;
let statusEl: HTMLDivElement;
let chartEl: HTMLDivElement;

let theme: Theme = 'dark';
try {
  theme = (localStorage.getItem('index-chart-theme') as Theme) || 'dark';
} catch {
  theme = 'dark';
}

let chart: echarts.ECharts | null = null;
const dataFile = INDEX_DATA;

// 看板取色表：按全标的列表顺序稳定取色，checkbox / 图线 / 悬浮提示共用同一张表
const dashColorBySymbol = new Map<string, string>(
  dataFile.meta.instruments.map((m, i) => [
    m.symbol,
    DASH_COLORS[i % DASH_COLORS.length],
  ]),
);

// ---- 单指数视图状态 ----
let curMeta: InstrumentMeta | null = null;
let curSymbol = 'SH.000001';
let curDaily: IndexBar[] = [];
let curAgg: IndexBar[] = [];
let curAggSpans: Array<[number, number]> = [];
let curAggMa: Record<MaSpan, (number | null)[]> | null = null;
let curTf: Timeframe = '1D';
const enabledMAs = new Set<MaSpan>([5, 10, 20, 60]);
let activeRange: RangeKey = '1y';
let programmaticZoom = false;
let singleZoom: [number, number] | null = null;

// ---- 对照看板状态 ----
let viewMode: ViewMode = 'single';
// 支持 ?view=dash 直接打开对照看板（也便于深链/调试）
try {
  if (new URLSearchParams(window.location.search).get('view') === 'dash') {
    viewMode = 'dash';
  }
} catch {
  /* 忽略解析失败 */
}
const dashSymbols = new Set<string>(['SH.000001', 'SZ.399001', 'SZ.399006']); // 三大板指默认勾选
let dashMode: DashMode = 'close';
let dashMaSpan: MaSpan = 20;
let dashInsts: DashInstrument[] = [];
let dashDates: string[] = [];
let dashBarMaps: Array<Map<string, IndexBar>> = [];
let dashZoom: { start: number; end: number } | null = null;
let dashRebuildTimer: ReturnType<typeof setTimeout> | undefined;

function pal(): ThemePalette {
  return THEMES[theme];
}

function nameOf(symbol: string): string | undefined {
  return dataFile.meta.instruments.find((m) => m.symbol === symbol)?.name;
}

function getDz(): { start: number; end: number } {
  const opt = chart?.getOption() as
    | { dataZoom?: Array<{ start?: number; end?: number }> }
    | undefined;
  const dz = opt?.dataZoom;
  return {
    start: dz && dz.length > 0 ? dz[0].start ?? 0 : 0,
    end: dz && dz.length > 0 ? dz[0].end ?? 100 : 100,
  };
}

// ---------------------------------------------------------------- MA 计算

function computeMaBySpan(closes: number[]): Record<MaSpan, (number | null)[]> {
  const result = {} as Record<MaSpan, (number | null)[]>;
  for (const span of MA_SPANS) result[span] = sma(closes, span);
  return result;
}

function setAggregated(tf: Timeframe): void {
  const agg = aggregateDaily(curDaily, tf);
  curAgg = agg.bars;
  curAggSpans = agg.spans;
  curTf = tf;
  curAggMa = computeMaBySpan(curAgg.map((b) => b.c));
}

function dailyIndexForDate(dateStr: string, mode: 'gte' | 'lte'): number {
  if (mode === 'gte') {
    const i = curDaily.findIndex((b) => b.d >= dateStr);
    return i < 0 ? 0 : i;
  }
  for (let i = curDaily.length - 1; i >= 0; i--) {
    if (curDaily[i].d <= dateStr) return i;
  }
  return curDaily.length - 1;
}

// ---------------------------------------------------------------- 单指数图表

function buildSeries(): SeriesOption[] {
  const p = pal();
  const series: SeriesOption[] = [
    {
      id: 'candle',
      name: curMeta?.name ?? '指数',
      type: 'candlestick',
      data: curAgg.map((b) => [b.o, b.c, b.l, b.h]),
      itemStyle: {
        color: p.up,
        color0: p.down,
        borderColor: p.up,
        borderColor0: p.down,
      },
      z: 2,
    },
  ];

  if (curAggMa) {
    for (const span of MA_SPANS) {
      if (!enabledMAs.has(span)) continue;
      series.push({
        id: `MA${span}`,
        name: `MA${span}`,
        type: 'line',
        data: curAggMa[span],
        smooth: true,
        showSymbol: false,
        connectNulls: false,
        lineStyle: { width: 1.4, color: p.ma[span] },
        itemStyle: { color: p.ma[span] },
        emphasis: { disabled: true },
        z: 3,
      });
    }
  }

  return series;
}

function buildOption(): EChartsOption {
  const p = pal();
  return {
    backgroundColor: p.bg,
    animation: false,
    grid: { left: 72, right: 24, top: 20, bottom: 74 },
    xAxis: {
      type: 'category',
      data: curAgg.map((b) => b.d),
      boundaryGap: true,
      axisLine: { lineStyle: { color: p.axisLine } },
      axisLabel: {
        color: p.dim,
        hideOverlap: true,
        formatter: (value: string) => {
          if (curTf === '1M') return value.slice(0, 7);
          if (curTf === '1Y') return value.slice(0, 4);
          return value;
        },
      },
      axisTick: { show: false },
      splitLine: { show: false },
      min: 'dataMin',
      max: 'dataMax',
    },
    yAxis: {
      scale: true,
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: p.dim },
      splitLine: { lineStyle: { color: p.splitLine } },
    },
    dataZoom: [
      {
        type: 'inside',
        start: 0,
        end: 100,
        zoomOnMouseWheel: true,
        moveOnMouseMove: true,
        moveOnMouseWheel: false,
      },
      {
        type: 'slider',
        start: 0,
        end: 100,
        height: 24,
        bottom: 12,
        borderColor: p.border,
        backgroundColor: p.panel,
        fillerColor: 'rgba(79,142,247,0.16)',
        dataBackground: {
          lineStyle: { color: p.axisLine },
          areaStyle: { color: p.panel },
        },
        selectedDataBackground: {
          lineStyle: { color: p.dim },
          areaStyle: { color: p.splitLine },
        },
        handleStyle: { color: p.dim },
        moveHandleStyle: { color: p.dim },
        textStyle: { color: p.dim },
      },
    ],
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'cross',
        lineStyle: { color: p.dim },
        label: {
          backgroundColor: p.tooltipBg,
          color: p.text,
          borderColor: p.tooltipBorder,
        },
        crossStyle: { color: p.dim },
      },
      backgroundColor: p.tooltipBg,
      borderColor: p.tooltipBorder,
      borderWidth: 1,
      textStyle: { color: p.text },
      extraCssText: 'box-shadow:0 8px 24px rgba(0,0,0,.28);border-radius:8px;',
      formatter: (params: unknown) => formatTooltip(params),
    },
    series: buildSeries(),
  };
}

function formatTooltip(params: unknown): string {
  const p = pal();
  const list = params as Array<{ dataIndex: number; seriesType: string }>;
  const candle = list.find((x) => x.seriesType === 'candlestick');
  if (!candle) return '';
  const i = candle.dataIndex;
  const bar = curAgg[i];
  if (!bar) return '';

  const prevClose = i > 0 ? curAgg[i - 1].c : null;
  const chg = prevClose == null ? null : ((bar.c - prevClose) / prevClose) * 100;
  const chgColor = chg == null ? p.dim : chg >= 0 ? p.up : p.down;
  const chgStr = chg == null ? '—' : `${chg >= 0 ? '+' : ''}${chg.toFixed(2)}%`;

  const rows: string[] = [];
  rows.push(
    `<div style="font-weight:600;margin-bottom:4px">${bar.d} · ${curMeta?.name ?? ''} · ${TF_LABEL[curTf]}</div>`,
  );
  rows.push(
    `<div style="display:flex;gap:14px"><span>开 <b>${bar.o.toFixed(2)}</b></span><span>高 <b>${bar.h.toFixed(2)}</b></span></div>`,
  );
  rows.push(
    `<div style="display:flex;gap:14px"><span>低 <b>${bar.l.toFixed(2)}</b></span><span>收 <b>${bar.c.toFixed(2)}</b></span></div>`,
  );
  rows.push(`<div style="color:${chgColor}">涨跌幅 ${chgStr}</div>`);

  if (curAggMa) {
    const maLines = MA_SPANS.filter((s) => enabledMAs.has(s))
      .map((s) => {
        const v = curAggMa![s][i];
        return v == null
          ? null
          : `<span style="color:${p.ma[s]}">MA${s} ${v.toFixed(2)}</span>`;
      })
      .filter((x): x is string => x != null);
    if (maLines.length > 0) {
      rows.push(
        `<div style="margin-top:4px;display:flex;gap:10px;flex-wrap:wrap">${maLines.join('')}</div>`,
      );
    }
  }

  return rows.join('');
}

// ---------------------------------------------------------------- 单指数缩放 / 粒度

function dispatchZoomPct(sIdx: number, eIdx: number): void {
  if (!chart || curAgg.length <= 1) return;
  const n = curAgg.length;
  const start = (Math.max(0, sIdx) / (n - 1)) * 100;
  const end = (Math.min(n - 1, eIdx) / (n - 1)) * 100;
  programmaticZoom = true;
  chart.dispatchAction({ type: 'dataZoom', start, end });
  programmaticZoom = false;
}

function zoomToDailyRange(startDaily: number, endDaily: number): void {
  const n = curAgg.length;
  let sIdx = curAggSpans.findIndex((sp) => sp[1] >= startDaily);
  if (sIdx < 0) sIdx = 0;
  let eIdx = -1;
  for (let i = 0; i < n; i++) if (curAggSpans[i][0] <= endDaily) eIdx = i;
  if (eIdx < 0) eIdx = n - 1;
  dispatchZoomPct(sIdx, eIdx);
}

function rebuildWithTimeframe(tf: Timeframe, startDaily: number, endDaily: number): void {
  if (!chart) return;
  setAggregated(tf);
  chart.setOption(buildOption(), { notMerge: true });
  zoomToDailyRange(startDaily, endDaily);
  renderReadout();
  updateStatus();
}

function applyViewWindow(fromDate: string, toDate: string): void {
  if (!chart || curDaily.length === 0) return;
  const startDaily = dailyIndexForDate(fromDate, 'gte');
  const endDaily = dailyIndexForDate(toDate, 'lte');
  const visibleDays = endDaily - startDaily + 1;
  const tf = tfForDays(visibleDays);
  if (tf === curTf) {
    zoomToDailyRange(startDaily, endDaily);
  } else {
    rebuildWithTimeframe(tf, startDaily, endDaily);
  }
}

function handleZoomChange(): void {
  if (!chart || curAgg.length === 0) return;
  const dz = getDz();
  const n = curAgg.length;
  const firstIdx = Math.max(0, Math.min(n - 1, Math.floor((dz.start / 100) * (n - 1))));
  const lastIdx = Math.max(0, Math.min(n - 1, Math.ceil((dz.end / 100) * (n - 1))));
  const startDaily = curAggSpans[firstIdx][0];
  const endDaily = curAggSpans[lastIdx][1];
  const visibleDays = endDaily - startDaily + 1;
  const tf = timeframeForVisibleDays(visibleDays, curTf);
  if (tf !== curTf) rebuildWithTimeframe(tf, startDaily, endDaily);
}

// ---------------------------------------------------------------- 对照看板

function defaultDashZoom(): { start: number; end: number } {
  const n = dashDates.length - 1;
  if (n <= 0) return { start: 0, end: 100 };
  const lastDate = dashDates[dashDates.length - 1];
  const from = new Date(`${lastDate}T00:00:00Z`);
  from.setUTCFullYear(from.getUTCFullYear() - 3);
  const fromStr = from.toISOString().slice(0, 10);
  const idx = Math.max(0, dashDates.findIndex((d) => d >= fromStr));
  return { start: (idx / n) * 100, end: 100 };
}

function dashModeLabel(): string {
  return dashMode === 'candle' ? '归一化蜡烛' : dashMode === 'ma' ? '归一化均线' : '归一化收盘';
}

function buildDashOption(): EChartsOption {
  const p = pal();
  const win = dashWindowFromPct(dashDates, dashZoom!.start, dashZoom!.end);
  const windowStart = dashDates[win.startIdx];
  return {
    backgroundColor: p.bg,
    animation: false,
    grid: { left: 72, right: 24, top: 20, bottom: 74 },
    xAxis: {
      type: 'category',
      data: dashDates,
      boundaryGap: true,
      axisLine: { lineStyle: { color: p.axisLine } },
      axisLabel: {
        color: p.dim,
        formatter: (value: string) => value.slice(0, 7),
      },
      axisTick: { show: false },
      splitLine: { show: false },
      min: 'dataMin',
      max: 'dataMax',
    },
    yAxis: {
      scale: true,
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: p.dim },
      splitLine: { lineStyle: { color: p.splitLine } },
    },
    dataZoom: [
      {
        type: 'inside',
        start: dashZoom!.start,
        end: dashZoom!.end,
        zoomOnMouseWheel: true,
        moveOnMouseMove: true,
        moveOnMouseWheel: false,
      },
      {
        type: 'slider',
        start: dashZoom!.start,
        end: dashZoom!.end,
        height: 24,
        bottom: 12,
        borderColor: p.border,
        backgroundColor: p.panel,
        fillerColor: 'rgba(79,142,247,0.16)',
        dataBackground: {
          lineStyle: { color: p.axisLine },
          areaStyle: { color: p.panel },
        },
        selectedDataBackground: {
          lineStyle: { color: p.dim },
          areaStyle: { color: p.splitLine },
        },
        handleStyle: { color: p.dim },
        moveHandleStyle: { color: p.dim },
        textStyle: { color: p.dim },
      },
    ],
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'cross',
        lineStyle: { color: p.dim },
        label: { backgroundColor: p.tooltipBg, color: p.text, borderColor: p.tooltipBorder },
        crossStyle: { color: p.dim },
      },
      backgroundColor: p.tooltipBg,
      borderColor: p.tooltipBorder,
      borderWidth: 1,
      textStyle: { color: p.text },
      extraCssText: 'box-shadow:0 8px 24px rgba(0,0,0,.28);border-radius:8px;',
      formatter: (params: unknown) => dashTooltipParams(params),
    },
    series: buildDashSeries(dashInsts, dashDates, {
      mode: dashMode,
      maSpan: dashMaSpan,
      windowStart,
      colors: dashColorBySymbol,
    }),
  };
}

function dashTooltipParams(params: unknown): string {
  const list = params as Array<{ dataIndex: number }>;
  if (!list.length || dashDates.length === 0) return '';
  const i = list[0].dataIndex;
  const win = dashWindowFromPct(dashDates, dashZoom!.start, dashZoom!.end);
  const p = pal();
  return dashTooltipHtml(
    dashInsts,
    dashBarMaps,
    dashDates,
    i,
    dashDates[win.startIdx],
    dashColorBySymbol,
    { text: p.text, dim: p.dim, up: p.up, down: p.down },
  );
}

function dashRenderFull(): void {
  if (!chart) return;
  dashZoom = dashZoom ?? defaultDashZoom();

  const selected = [...dashSymbols].filter((s) => dataFile.series[s]);
  dashInsts = selected.map((s) => ({
    symbol: s,
    name: nameOf(s) ?? s,
    bars: dataFile.series[s],
  }));
  dashDates = buildSharedDates(dashInsts);
  dashBarMaps = buildBarMaps(dashInsts);

  if (dashInsts.length === 0 || dashDates.length === 0) {
    statusEl.innerHTML = '<span class="warn">对照看板：请至少勾选一个标的。</span>';
    chart.setOption(
      {
        backgroundColor: pal().bg,
        grid: { left: 72, right: 24, top: 20, bottom: 74 },
        xAxis: { type: 'category', data: [] },
        yAxis: { scale: true },
        series: [],
      } as EChartsOption,
      { notMerge: true },
    );
    return;
  }

  chart.setOption(buildDashOption(), { notMerge: true });
  updateDashRangeButtons();
  updateStatus();
}

function dashRenderSeries(): void {
  if (!chart || dashDates.length === 0 || !dashZoom) return;
  const win = dashWindowFromPct(dashDates, dashZoom.start, dashZoom.end);
  const windowStart = dashDates[win.startIdx];
  chart.setOption({
    series: buildDashSeries(dashInsts, dashDates, {
      mode: dashMode,
      maSpan: dashMaSpan,
      windowStart,
      colors: dashColorBySymbol,
    }),
  });
}

function dashZoomRange(range: RangeKey): void {
  if (!chart || dashDates.length === 0) return;
  if (range === 'custom') return;

  const lastDate = dashDates[dashDates.length - 1];
  let startPct = 0;
  if (range !== 'all') {
    const years = range === '5y' ? 5 : range === '3y' ? 3 : 1;
    const from = new Date(`${lastDate}T00:00:00Z`);
    from.setUTCFullYear(from.getUTCFullYear() - years);
    const fromStr = from.toISOString().slice(0, 10);
    const idx = Math.max(0, dashDates.findIndex((d) => d >= fromStr));
    const n = dashDates.length - 1;
    startPct = (idx / n) * 100;
  }

  dashZoom = { start: startPct, end: 100 };
  programmaticZoom = true;
  chart.dispatchAction({ type: 'dataZoom', start: startPct, end: 100 });
  programmaticZoom = false;
  dashRenderSeries();
  updateDashRangeButtons(range);
}

function updateDashRangeButtons(active: RangeKey = 'custom'): void {
  for (const btn of Array.from(dashRangeEl.querySelectorAll('button'))) {
    btn.classList.toggle('active', btn.dataset.range === active);
  }
}

// ---------------------------------------------------------------- 视图切换

function switchToSingle(): void {
  if (viewMode === 'single' || !chart) return;
  dashZoom = getDz();
  viewMode = 'single';
  controlsSingleEl.hidden = false;
  controlsDashEl.hidden = true;
  readoutEl.hidden = false;

  renderIndex(curSymbol);
  if (singleZoom) {
    programmaticZoom = true;
    chart.dispatchAction({ type: 'dataZoom', start: singleZoom[0], end: singleZoom[1] });
    programmaticZoom = false;
    activeRange = 'custom';
    updateRangeButtons();
  }
  updateStatus();
}

function switchToDash(): void {
  // 注意：不能因 viewMode 已是 'dash' 而提前 return——?view=dash 深链路径
  // 需要强制完成一次看板渲染。
  singleZoom = [getDz().start, getDz().end];
  viewMode = 'dash';
  controlsSingleEl.hidden = true;
  controlsDashEl.hidden = false;
  readoutEl.hidden = true;
  dashRenderFull();
}

// ---------------------------------------------------------------- 读数条 & 状态

function renderReadout(): void {
  if (!curMeta || curDaily.length === 0 || !curAggMa) {
    readoutEl.innerHTML = '';
    return;
  }
  const p = pal();
  const bar = curDaily[curDaily.length - 1];
  const prev = curDaily[curDaily.length - 2]?.c;
  const chg = prev == null ? null : ((bar.c - prev) / prev) * 100;
  const chgColor = chg == null ? p.dim : chg >= 0 ? p.up : p.down;
  const chgStr = chg == null ? '—' : `${chg >= 0 ? '+' : ''}${chg.toFixed(2)}%`;

  const lastIdx = curAggMa['5'].length - 1;
  const maChips = MA_SPANS.filter((s) => enabledMAs.has(s))
    .map((s) => {
      const v = curAggMa![s][lastIdx];
      return v == null
        ? ''
        : `<span class="readout-ma-item" style="color:${p.ma[s]}">MA${s} ${v.toFixed(2)}</span>`;
    })
    .join('');

  readoutEl.innerHTML =
    `<span class="readout-tf">${TF_LABEL[curTf]}</span>` +
    `<div class="readout-name">${curMeta.name}<span class="readout-code">${curMeta.symbol}</span></div>` +
    `<div class="readout-price" style="color:${chgColor}">${bar.c.toFixed(2)}</div>` +
    `<div class="readout-chg" style="color:${chgColor}">${chgStr}</div>` +
    (maChips ? `<div class="readout-ma">${maChips}</div>` : '');
}

function updateStatus(): void {
  if (viewMode === 'dash') {
    const modeText = dashMode === 'ma' ? `归一化均线 MA${dashMaSpan}` : dashModeLabel();
    statusEl.innerHTML =
      `对照看板 · ${dashInsts.length} 个标的 · 归一化基准=可见窗口起点 100 · 对比方式 ${modeText}` +
      ` · 数据源 ${dataFile.meta.source} · 滚轮缩放 / 拖拽平移 / 双击复位`;
    return;
  }
  if (!curMeta) return;
  const gapNote =
    curMeta.start > '2005-01-04'
      ? `<span class="warn">（本库该指数最早仅到 ${curMeta.start}）</span>`
      : '';
  statusEl.innerHTML =
    `${curMeta.name} ${curMeta.symbol}：${curMeta.start} ~ ${curMeta.end}（${curDaily.length} 根日线）` +
    ` · 当前视图 ${TF_LABEL[curTf]}（${curAgg.length} 根）` +
    ` · 数据源 ${dataFile.meta.source} · 滚轮缩放 / 拖拽平移 / 双击复位` +
    ` ${gapNote}`;
}

// ---------------------------------------------------------------- 交互（单指数）

function renderIndex(symbol: string): void {
  const meta = dataFile.meta.instruments.find((m) => m.symbol === symbol && m.kind === 'index');
  const bars = dataFile.series[symbol];
  if (!meta || !bars || !chart) return;

  curMeta = meta;
  curSymbol = symbol;
  curDaily = bars;
  setAggregated('1D');
  activeRange = '1y';

  chart.setOption(buildOption(), { notMerge: true });
  updateRangeButtons();

  const lastDate = curDaily[curDaily.length - 1].d;
  const last = new Date(`${lastDate}T00:00:00Z`);
  const from = new Date(last);
  from.setUTCFullYear(from.getUTCFullYear() - 1);
  applyViewWindow(from.toISOString().slice(0, 10), lastDate);

  renderReadout();
  updateStatus();
}

function onMaToggle(span: MaSpan, checked: boolean): void {
  if (checked) enabledMAs.add(span);
  else enabledMAs.delete(span);
  chart?.setOption({ series: buildSeries() });
  renderReadout();
}

function zoomRange(range: RangeKey): void {
  if (!chart || curDaily.length === 0) return;
  if (range === 'custom') return;

  const lastDate = curDaily[curDaily.length - 1].d;
  let fromDate = curDaily[0].d;
  if (range !== 'all') {
    const years = range === '5y' ? 5 : range === '3y' ? 3 : 1;
    const last = new Date(`${lastDate}T00:00:00Z`);
    const from = new Date(last);
    from.setUTCFullYear(from.getUTCFullYear() - years);
    fromDate = from.toISOString().slice(0, 10);
  }

  programmaticZoom = true;
  activeRange = range;
  updateRangeButtons();
  applyViewWindow(fromDate, lastDate);
  programmaticZoom = false;
}

function applyTheme(): void {
  if (!chart) return;
  if (viewMode === 'dash') {
    dashRenderFull();
    updateThemeUI();
    return;
  }
  const { start, end } = getDz();
  chart.setOption(buildOption(), { notMerge: true });
  programmaticZoom = true;
  chart.dispatchAction({ type: 'dataZoom', start, end });
  programmaticZoom = false;
  updateThemeUI();
}

function updateThemeUI(): void {
  document.body.dataset.theme = theme;
  themeToggleEl.textContent = theme === 'dark' ? '☀️' : '🌙';
  for (const label of Array.from(maTogglesEl.querySelectorAll('label'))) {
    const span = Number(label.dataset.span) as MaSpan;
    const dot = label.querySelector('.dot') as HTMLElement | null;
    if (dot) dot.style.background = pal().ma[span];
  }
  renderReadout();
}

function updateRangeButtons(): void {
  for (const btn of Array.from(rangeButtonsEl.querySelectorAll('button'))) {
    btn.classList.toggle('active', btn.dataset.range === activeRange);
  }
}

function updateMaToggles(): void {
  for (const label of Array.from(maTogglesEl.querySelectorAll('label'))) {
    const span = Number(label.dataset.span) as MaSpan;
    label.classList.toggle('on', enabledMAs.has(span));
  }
}

// ---------------------------------------------------------------- UI 构建

function buildViewSwitch(): void {
  const options: Array<{ key: ViewMode; label: string }> = [
    { key: 'single', label: '单指数' },
    { key: 'dash', label: '对照看板' },
  ];
  for (const o of options) {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.textContent = o.label;
    btn.dataset.view = o.key;
    btn.classList.toggle('active', viewMode === o.key);
    btn.addEventListener('click', () => {
      for (const b of Array.from(viewSwitchEl.querySelectorAll('button'))) {
        b.classList.toggle('active', b === btn);
      }
      if (o.key === 'single') switchToSingle();
      else switchToDash();
    });
    viewSwitchEl.appendChild(btn);
  }
}

function buildIndexButtons(): void {
  const indices = dataFile.meta.instruments.filter((m) => m.kind === 'index');
  for (const meta of indices) {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.textContent = meta.name;
    btn.dataset.symbol = meta.symbol;
    btn.classList.toggle('active', meta.symbol === 'SH.000001');
    btn.addEventListener('click', () => {
      for (const b of Array.from(indexSwitchEl.querySelectorAll('button'))) {
        b.classList.toggle('active', b === btn);
      }
      renderIndex(meta.symbol);
    });
    indexSwitchEl.appendChild(btn);
  }
}

function buildMaToggles(): void {
  for (const span of MA_SPANS) {
    const label = document.createElement('label');
    label.dataset.span = String(span);
    label.classList.toggle('on', enabledMAs.has(span));

    const dot = document.createElement('span');
    dot.className = 'dot';
    dot.style.background = pal().ma[span];

    const input = document.createElement('input');
    input.type = 'checkbox';
    input.checked = enabledMAs.has(span);
    input.addEventListener('change', () => {
      onMaToggle(span, input.checked);
      updateMaToggles();
    });

    const text = document.createElement('span');
    text.textContent = `MA${span}`;

    label.append(dot, input, text);
    maTogglesEl.appendChild(label);
  }
}

function buildRangeButtons(): void {
  const ranges: Array<{ key: RangeKey; label: string }> = [
    { key: 'all', label: '全部' },
    { key: '5y', label: '5年' },
    { key: '3y', label: '3年' },
    { key: '1y', label: '1年' },
  ];
  for (const r of ranges) {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.textContent = r.label;
    btn.dataset.range = r.key;
    btn.addEventListener('click', () => zoomRange(r.key));
    rangeButtonsEl.appendChild(btn);
  }
}

function buildDashInstruments(): void {
  for (const meta of dataFile.meta.instruments) {
    const label = document.createElement('label');
    label.dataset.symbol = meta.symbol;
    label.classList.toggle('on', dashSymbols.has(meta.symbol));

    const dot = document.createElement('span');
    dot.className = 'dot';
    dot.style.background = dashColorBySymbol.get(meta.symbol) ?? '#8a827b';

    const input = document.createElement('input');
    input.type = 'checkbox';
    input.checked = dashSymbols.has(meta.symbol);
    input.addEventListener('change', () => {
      if (input.checked) dashSymbols.add(meta.symbol);
      else dashSymbols.delete(meta.symbol);
      label.classList.toggle('on', input.checked);
      dashRenderFull();
    });

    const text = document.createElement('span');
    const code = meta.symbol.split('.')[1];
    text.textContent = `${meta.name} ${code}`;

    label.append(dot, input, text);
    dashInstrumentsEl.appendChild(label);
  }
}

function buildDashMode(): void {
  const modes: Array<{ key: DashMode; label: string }> = [
    { key: 'candle', label: '蜡烛' },
    { key: 'close', label: '收盘' },
    { key: 'ma', label: '均线' },
  ];
  for (const m of modes) {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.textContent = m.label;
    btn.dataset.mode = m.key;
    btn.classList.toggle('active', dashMode === m.key);
    btn.addEventListener('click', () => {
      dashMode = m.key;
      dashMaSpanEl.hidden = dashMode !== 'ma';
      for (const b of Array.from(dashModeEl.querySelectorAll('button'))) {
        b.classList.toggle('active', b === btn);
      }
      dashRenderFull();
    });
    dashModeEl.appendChild(btn);
  }
}

function buildDashMaSpan(): void {
  for (const span of MA_SPANS) {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.textContent = `MA${span}`;
    btn.dataset.span = String(span);
    btn.classList.toggle('active', dashMaSpan === span);
    btn.addEventListener('click', () => {
      dashMaSpan = span;
      for (const b of Array.from(dashMaSpanEl.querySelectorAll('button'))) {
        b.classList.toggle('active', b === btn);
      }
      dashRenderSeries();
    });
    dashMaSpanEl.appendChild(btn);
  }
}

function buildDashRange(): void {
  const ranges: Array<{ key: RangeKey; label: string }> = [
    { key: 'all', label: '全部' },
    { key: '5y', label: '5年' },
    { key: '3y', label: '3年' },
    { key: '1y', label: '1年' },
  ];
  for (const r of ranges) {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.textContent = r.label;
    btn.dataset.range = r.key;
    btn.addEventListener('click', () => dashZoomRange(r.key));
    dashRangeEl.appendChild(btn);
  }
}

// ---------------------------------------------------------------- 启动

function main(): void {
  indexSwitchEl = document.getElementById('index-switch') as HTMLDivElement;
  maTogglesEl = document.getElementById('ma-toggles') as HTMLDivElement;
  rangeButtonsEl = document.getElementById('range-buttons') as HTMLDivElement;
  viewSwitchEl = document.getElementById('view-switch') as HTMLDivElement;
  controlsSingleEl = document.getElementById('controls-single') as HTMLElement;
  controlsDashEl = document.getElementById('controls-dash') as HTMLElement;
  dashInstrumentsEl = document.getElementById('dash-instruments') as HTMLDivElement;
  dashModeEl = document.getElementById('dash-mode') as HTMLDivElement;
  dashMaSpanEl = document.getElementById('dash-ma-span') as HTMLDivElement;
  dashRangeEl = document.getElementById('dash-range') as HTMLDivElement;
  themeToggleEl = document.getElementById('theme-toggle') as HTMLButtonElement;
  readoutEl = document.getElementById('readout') as HTMLDivElement;
  statusEl = document.getElementById('status') as HTMLDivElement;
  chartEl = document.getElementById('chart') as HTMLDivElement;

  if (!dataFile.meta.instruments.length) {
    statusEl.innerHTML =
      '<span class="warn">未找到目标数据，请先运行 npm run extract。</span>';
    return;
  }

  buildViewSwitch();
  buildIndexButtons();
  buildMaToggles();
  buildRangeButtons();
  buildDashInstruments();
  buildDashMode();
  buildDashMaSpan();
  buildDashRange();
  updateThemeUI();

  themeToggleEl.addEventListener('click', () => {
    theme = theme === 'dark' ? 'light' : 'dark';
    try {
      localStorage.setItem('index-chart-theme', theme);
    } catch {
      /* file:// 下 localStorage 可能不可用，忽略 */
    }
    applyTheme();
  });

  chart = echarts.init(chartEl);
  chart.on('datazoom', () => {
    if (programmaticZoom) return;
    activeRange = 'custom';
    updateRangeButtons();
    if (viewMode === 'single') {
      handleZoomChange();
    } else {
      dashZoom = getDz();
      clearTimeout(dashRebuildTimer);
      dashRebuildTimer = setTimeout(dashRenderSeries, 80);
    }
  });
  chart.on('dblclick', () => {
    if (viewMode === 'single') zoomRange('all');
    else dashZoomRange('all');
  });
  window.addEventListener('resize', () => chart?.resize());

  // 默认展示上证指数；若缺失则回退到第一个可用指数。深链 ?view=dash 直接进看板。
  const initial =
    dataFile.meta.instruments.find((m) => m.symbol === 'SH.000001')?.symbol ??
    dataFile.meta.instruments[0].symbol;
  if (viewMode === 'dash') {
    switchToDash();
  } else {
    renderIndex(initial);
  }
}

// 构建产物可能把脚本放在 <head>（DOM 尚未就绪），因此统一等 DOM 就绪再启动。
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', main);
} else {
  main();
}
