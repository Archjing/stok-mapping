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
import { INDEX_DATA } from './generated/data';
import type { IndexBar, IndexMeta } from './data-types';
import './styles.css';

echarts.use([
  CandlestickChart,
  LineChart,
  GridComponent,
  TooltipComponent,
  DataZoomComponent,
  CanvasRenderer,
]);

const MA_SPANS = [5, 10, 20, 30, 60] as const;
type MaSpan = (typeof MA_SPANS)[number];
type Theme = 'dark' | 'light';
type RangeKey = 'all' | '5y' | '3y' | '1y' | 'custom';

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
    bg: '#121823',
    panel: '#121823',
    border: '#232d3d',
    text: '#e6edf3',
    dim: '#8b98a9',
    axisLine: '#2b3446',
    splitLine: '#1a2230',
    tooltipBg: '#151c28',
    tooltipBorder: '#2b3446',
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
    bg: '#ffffff',
    panel: '#ffffff',
    border: '#e2e8f0',
    text: '#1f2937',
    dim: '#64748b',
    axisLine: '#cbd5e1',
    splitLine: '#eef2f7',
    tooltipBg: '#ffffff',
    tooltipBorder: '#dbe3ec',
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
let curMeta: IndexMeta | null = null;
let curDaily: IndexBar[] = []; // 原始日线（单一事实源）
let curAgg: IndexBar[] = []; // 当前视图粒度的 K 线（1D/1W/1M/1Y 聚合）
let curAggSpans: Array<[number, number]> = []; // 每个聚合 bar 的日线索引区间
let curAggMa: Record<MaSpan, (number | null)[]> | null = null; // 聚合收盘的均线
let curTf: Timeframe = '1D';
const enabledMAs = new Set<MaSpan>([5, 10, 20, 60]);
let activeRange: RangeKey = '1y';
let programmaticZoom = false;

function pal(): ThemePalette {
  return THEMES[theme];
}

// ---------------------------------------------------------------- MA 计算

function sma(values: number[], period: number): (number | null)[] {
  const out: (number | null)[] = new Array(values.length).fill(null);
  let sum = 0;
  for (let i = 0; i < values.length; i++) {
    sum += values[i];
    if (i >= period) sum -= values[i - period];
    if (i >= period - 1) out[i] = sum / period;
  }
  return out;
}

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

/** 日线索引 → 日期；gte=首个 >= 该日期的索引，lte=最后一个 <= 该日期的索引。 */
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

// ---------------------------------------------------------------- 图表构建

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

// ---------------------------------------------------------------- 缩放 / 粒度切换

/** 把某个聚合索引区间 [sIdx, eIdx] 转换为 dataZoom 百分比并派发。 */
function dispatchZoomPct(sIdx: number, eIdx: number): void {
  if (!chart || curAgg.length <= 1) return;
  const n = curAgg.length;
  const start = (Math.max(0, sIdx) / (n - 1)) * 100;
  const end = (Math.min(n - 1, eIdx) / (n - 1)) * 100;
  programmaticZoom = true;
  chart.dispatchAction({ type: 'dataZoom', start, end });
  programmaticZoom = false;
}

/** 按日线索引区间定位当前聚合轴上的可见区间，并应用缩放。 */
function zoomToDailyRange(startDaily: number, endDaily: number): void {
  const n = curAgg.length;
  let sIdx = curAggSpans.findIndex((sp) => sp[1] >= startDaily);
  if (sIdx < 0) sIdx = 0;
  let eIdx = -1;
  for (let i = 0; i < n; i++) if (curAggSpans[i][0] <= endDaily) eIdx = i;
  if (eIdx < 0) eIdx = n - 1;
  dispatchZoomPct(sIdx, eIdx);
}

/** 重建为指定粒度，并保持同一日线日期窗口。 */
function rebuildWithTimeframe(tf: Timeframe, startDaily: number, endDaily: number): void {
  if (!chart) return;
  setAggregated(tf);
  chart.setOption(buildOption(), { notMerge: true });
  zoomToDailyRange(startDaily, endDaily);
  renderReadout();
  updateStatus();
}

/** 把视图窗口设为 [fromDate, toDate]，按窗口宽度决定 K 线粒度。 */
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

/** dataZoom 事件：按当前可见宽度决定是否切换粒度（带迟滞）。 */
function handleZoomChange(): void {
  if (!chart || curAgg.length === 0) return;
  const opt = chart.getOption() as {
    dataZoom?: Array<{ start?: number; end?: number }>;
  };
  const dz = opt.dataZoom;
  if (!dz || dz.length === 0) return;
  const n = curAgg.length;
  const firstIdx = Math.max(
    0,
    Math.min(n - 1, Math.floor(((dz[0].start ?? 0) / 100) * (n - 1))),
  );
  const lastIdx = Math.max(
    0,
    Math.min(n - 1, Math.ceil(((dz[0].end ?? 100) / 100) * (n - 1))),
  );
  const startDaily = curAggSpans[firstIdx][0];
  const endDaily = curAggSpans[lastIdx][1];
  const visibleDays = endDaily - startDaily + 1;
  const tf = timeframeForVisibleDays(visibleDays, curTf);
  if (tf !== curTf) rebuildWithTimeframe(tf, startDaily, endDaily);
}

// ---------------------------------------------------------------- 读数条 & 状态

function renderReadout(): void {
  if (!curMeta || curDaily.length === 0 || !curAggMa) {
    readoutEl.innerHTML = '';
    return;
  }
  const p = pal();
  const bar = curDaily[curDaily.length - 1]; // 真实最新日线
  const prev = curDaily[curDaily.length - 2]?.c;
  const chg = prev == null ? null : ((bar.c - prev) / prev) * 100;
  const chgColor = chg == null ? p.dim : chg >= 0 ? p.up : p.down;
  const chgStr = chg == null ? '—' : `${chg >= 0 ? '+' : ''}${chg.toFixed(2)}%`;

  // 均线取当前粒度序列的最新值
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

// ---------------------------------------------------------------- 交互

function renderIndex(symbol: string): void {
  const meta = dataFile.meta.indices.find((m) => m.symbol === symbol);
  const bars = dataFile.series[symbol];
  if (!meta || !bars || !chart) return;

  curMeta = meta;
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
  // 仅替换 series（按 id 合并），保留当前缩放位置。
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
  const opt = chart.getOption() as {
    dataZoom?: Array<{ start?: number; end?: number }>;
  };
  const dz = opt.dataZoom;
  const start = dz && dz.length > 0 ? dz[0].start ?? 0 : 0;
  const end = dz && dz.length > 0 ? dz[0].end ?? 100 : 100;

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

// ---------------------------------------------------------------- UI 初始化

function buildIndexButtons(): void {
  for (const meta of dataFile.meta.indices) {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.textContent = meta.name;
    btn.dataset.symbol = meta.symbol;
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

// ---------------------------------------------------------------- 启动

function main(): void {
  indexSwitchEl = document.getElementById('index-switch') as HTMLDivElement;
  maTogglesEl = document.getElementById('ma-toggles') as HTMLDivElement;
  rangeButtonsEl = document.getElementById('range-buttons') as HTMLDivElement;
  themeToggleEl = document.getElementById('theme-toggle') as HTMLButtonElement;
  readoutEl = document.getElementById('readout') as HTMLDivElement;
  statusEl = document.getElementById('status') as HTMLDivElement;
  chartEl = document.getElementById('chart') as HTMLDivElement;

  if (!dataFile.meta.indices.length) {
    statusEl.innerHTML =
      '<span class="warn">未找到目标指数数据，请先运行 npm run extract。</span>';
    return;
  }

  buildIndexButtons();
  buildMaToggles();
  buildRangeButtons();
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
    if (!programmaticZoom) {
      activeRange = 'custom';
      updateRangeButtons();
      handleZoomChange();
    }
  });
  chart.on('dblclick', () => zoomRange('all'));
  window.addEventListener('resize', () => chart?.resize());

  // 默认展示上证指数；若库中缺失则回退到第一个可用指数。
  const initial =
    dataFile.meta.indices.find((m) => m.symbol === 'SH.000001')?.symbol ??
    dataFile.meta.indices[0].symbol;
  renderIndex(initial);
}

// 构建产物可能把脚本放在 <head>（DOM 尚未就绪），因此统一等 DOM 就绪再启动。
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', main);
} else {
  main();
}
