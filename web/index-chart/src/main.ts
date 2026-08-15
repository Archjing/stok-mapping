import * as echarts from 'echarts/core';
import { CandlestickChart, LineChart } from 'echarts/charts';
import {
  DataZoomComponent,
  GridComponent,
  TooltipComponent,
} from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
import type { EChartsOption, SeriesOption } from 'echarts';

import './styles.css';

echarts.use([
  CandlestickChart,
  LineChart,
  GridComponent,
  TooltipComponent,
  DataZoomComponent,
  CanvasRenderer,
]);

interface Bar {
  d: string;
  o: number;
  h: number;
  l: number;
  c: number;
}

interface IndexMeta {
  symbol: string;
  name: string;
  start: string;
  end: string;
  count: number;
}

interface DataFile {
  meta: {
    generatedAt: string;
    source: string;
    indices: IndexMeta[];
  };
  series: Record<string, Bar[]>;
}

const MA_SPANS = [5, 10, 20, 30, 60] as const;
type MaSpan = (typeof MA_SPANS)[number];

const MA_COLORS: Record<MaSpan, string> = {
  5: '#f6d365',
  10: '#ff8fab',
  20: '#b388ff',
  30: '#6ee7b7',
  60: '#4fc3f7',
};

const CANDLE_UP = '#ef232a'; // A股习惯：红涨
const CANDLE_DOWN = '#14b143'; // A股习惯：绿跌

type RangeKey = 'all' | '5y' | '3y' | '1y' | 'custom';

const indexSwitchEl = document.getElementById('index-switch') as HTMLDivElement;
const maTogglesEl = document.getElementById('ma-toggles') as HTMLDivElement;
const rangeButtonsEl = document.getElementById('range-buttons') as HTMLDivElement;
const statusEl = document.getElementById('status') as HTMLDivElement;
const chartEl = document.getElementById('chart') as HTMLDivElement;

let chart: echarts.ECharts | null = null;
let dataFile: DataFile | null = null;
let curMeta: IndexMeta | null = null;
let curBars: Bar[] = [];
let curMa: Record<MaSpan, (number | null)[]> | null = null;
const enabledMAs = new Set<MaSpan>([5, 10, 20, 60]);
let activeRange: RangeKey = 'all';
let programmaticZoom = false;

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

function computeMaBySpan(bars: Bar[]): Record<MaSpan, (number | null)[]> {
  const closes = bars.map((b) => b.c);
  const result = {} as Record<MaSpan, (number | null)[]>;
  for (const span of MA_SPANS) result[span] = sma(closes, span);
  return result;
}

// ---------------------------------------------------------------- 图表构建

function buildSeries(): SeriesOption[] {
  const series: SeriesOption[] = [
    {
      id: 'candle',
      name: curMeta?.name ?? '指数',
      type: 'candlestick',
      data: curBars.map((b) => [b.o, b.c, b.l, b.h]),
      itemStyle: {
        color: CANDLE_UP,
        color0: CANDLE_DOWN,
        borderColor: CANDLE_UP,
        borderColor0: CANDLE_DOWN,
      },
      z: 2,
    },
  ];

  if (curMa) {
    for (const span of MA_SPANS) {
      if (!enabledMAs.has(span)) continue;
      series.push({
        id: `MA${span}`,
        name: `MA${span}`,
        type: 'line',
        data: curMa[span],
        smooth: true,
        showSymbol: false,
        connectNulls: false,
        lineStyle: { width: 1.4, color: MA_COLORS[span] },
        itemStyle: { color: MA_COLORS[span] },
        emphasis: { disabled: true },
        z: 3,
      });
    }
  }

  return series;
}

function buildOption(): EChartsOption {
  return {
    backgroundColor: '#0d1117',
    animation: false,
    grid: { left: 70, right: 24, top: 18, bottom: 70 },
    xAxis: {
      type: 'category',
      data: curBars.map((b) => b.d),
      boundaryGap: true,
      axisLine: { lineStyle: { color: '#2b3446' } },
      axisLabel: { color: '#8b98a9', hideOverlap: true },
      axisTick: { show: false },
      splitLine: { show: false },
      min: 'dataMin',
      max: 'dataMax',
    },
    yAxis: {
      scale: true,
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: '#8b98a9' },
      splitLine: { lineStyle: { color: '#1c2431' } },
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
        bottom: 10,
        borderColor: '#2b3446',
        backgroundColor: '#141a24',
        fillerColor: 'rgba(31,111,235,0.18)',
        dataBackground: {
          lineStyle: { color: '#2b3446' },
          areaStyle: { color: '#141a24' },
        },
        selectedDataBackground: {
          lineStyle: { color: '#3a4a63' },
          areaStyle: { color: '#1c2431' },
        },
        handleStyle: { color: '#8b98a9' },
        moveHandleStyle: { color: '#d0d7de' },
        textStyle: { color: '#8b98a9' },
      },
    ],
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'cross',
        lineStyle: { color: '#3a4a63' },
        label: { backgroundColor: '#1f2430', color: '#e6edf3' },
        crossStyle: { color: '#3a4a63' },
      },
      backgroundColor: '#1f2430',
      borderColor: '#333c4d',
      textStyle: { color: '#e6edf3' },
      formatter: (params: unknown) => formatTooltip(params),
    },
    series: buildSeries(),
  };
}

function formatTooltip(params: unknown): string {
  const list = params as Array<{
    dataIndex: number;
    seriesType: string;
    color?: string;
    seriesName?: string;
  }>;
  const candle = list.find((p) => p.seriesType === 'candlestick');
  if (!candle) return '';
  const i = candle.dataIndex;
  const bar = curBars[i];
  if (!bar) return '';

  const prevClose = i > 0 ? curBars[i - 1].c : null;
  const chg =
    prevClose == null
      ? null
      : ((bar.c - prevClose) / prevClose) * 100;
  const chgColor = chg == null ? '#8b98a9' : chg >= 0 ? CANDLE_UP : CANDLE_DOWN;
  const chgStr =
    chg == null ? '—' : `${chg >= 0 ? '+' : ''}${chg.toFixed(2)}%`;

  const rows: string[] = [];
  rows.push(
    `<div style="font-weight:600;margin-bottom:4px">${bar.d} · ${curMeta?.name ?? ''}</div>`,
  );
  rows.push(
    `<div>开 <b>${bar.o.toFixed(2)}</b>　高 <b>${bar.h.toFixed(2)}</b></div>`,
  );
  rows.push(
    `<div>低 <b>${bar.l.toFixed(2)}</b>　收 <b>${bar.c.toFixed(2)}</b></div>`,
  );
  rows.push(
    `<div style="color:${chgColor}">涨跌幅 ${chgStr}</div>`,
  );

  if (curMa) {
    const maLines = MA_SPANS.filter((s) => enabledMAs.has(s))
      .map((s) => {
        const v = curMa![s][i];
        return v == null
          ? null
          : `<span style="color:${MA_COLORS[s]}">MA${s} ${v.toFixed(2)}</span>`;
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

// ---------------------------------------------------------------- 交互

function updateStatus(): void {
  if (!dataFile || !curMeta) return;
  const meta = curMeta;
  // 若某指数本库数据早于 2005 即缺失，动态提示其实际起点。
  const gapNote =
    meta.start > '2005-01-01'
      ? `<span class="warn">（本库该指数最早仅到 ${meta.start}）</span>`
      : '';
  statusEl.innerHTML =
    `当前：<b>${meta.name}</b> ${meta.symbol} · ` +
    `${meta.start} ~ ${meta.end} · ${meta.count} 根日线 · ` +
    `来源 ${dataFile.meta.source} ${gapNote}`;
}

function renderIndex(symbol: string): void {
  const file = dataFile;
  const meta = file?.meta.indices.find((m) => m.symbol === symbol);
  const bars = file?.series[symbol];
  if (!file || !meta || !bars || !chart) return;

  curMeta = meta;
  curBars = bars;
  curMa = computeMaBySpan(bars);
  activeRange = 'all';

  chart.setOption(buildOption(), { notMerge: true });
  updateRangeButtons();
  updateStatus();
}

function onMaToggle(span: MaSpan, checked: boolean): void {
  if (checked) enabledMAs.add(span);
  else enabledMAs.delete(span);
  // 仅替换 series（按 id 合并），保留当前缩放位置。
  chart?.setOption({ series: buildSeries() });
}

function zoomRange(range: RangeKey): void {
  if (!chart || curBars.length === 0) return;
  if (range === 'custom') return;

  programmaticZoom = true;
  activeRange = range;
  updateRangeButtons();

  if (range === 'all') {
    chart.dispatchAction({ type: 'dataZoom', start: 0, end: 100 });
    programmaticZoom = false;
    return;
  }

  const years = range === '5y' ? 5 : range === '3y' ? 3 : 1;
  const last = new Date(`${curBars[curBars.length - 1].d}T00:00:00`);
  const from = new Date(last);
  from.setFullYear(from.getFullYear() - years);
  const fromStr = from.toISOString().slice(0, 10);

  let startIdx = curBars.findIndex((b) => b.d >= fromStr);
  if (startIdx < 0) startIdx = 0;

  const total = curBars.length - 1;
  const startPct = (startIdx / total) * 100;
  chart.dispatchAction({ type: 'dataZoom', start: startPct, end: 100 });
  programmaticZoom = false;
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
  const metas = dataFile?.meta.indices ?? [];
  for (const meta of metas) {
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
    dot.style.background = MA_COLORS[span];

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
    btn.classList.toggle('active', r.key === 'all');
    btn.addEventListener('click', () => zoomRange(r.key));
    rangeButtonsEl.appendChild(btn);
  }
}

// ---------------------------------------------------------------- 启动

async function main(): Promise<void> {
  try {
    const resp = await fetch(`${import.meta.env.BASE_URL}indices.json`);
    if (!resp.ok) {
      throw new Error(`加载 indices.json 失败（HTTP ${resp.status}），请先运行 npm run extract`);
    }
    dataFile = (await resp.json()) as DataFile;
  } catch (err) {
    statusEl.innerHTML = `<span class="warn">${(err as Error).message}</span>`;
    return;
  }

  if (!dataFile.meta.indices.length) {
    statusEl.innerHTML = '<span class="warn">数据库中未找到任何目标指数数据。</span>';
    return;
  }

  buildIndexButtons();
  buildMaToggles();
  buildRangeButtons();

  chart = echarts.init(chartEl);
  chart.on('datazoom', () => {
    if (!programmaticZoom) {
      activeRange = 'custom';
      updateRangeButtons();
    }
  });

  window.addEventListener('resize', () => chart?.resize());

  // 默认展示上证指数；若库中缺失则回退到第一个可用指数。
  const first = dataFile.meta.indices[0].symbol;
  const initial =
    dataFile.meta.indices.find((m) => m.symbol === 'SH.000001')?.symbol ?? first;
  renderIndex(initial);
}

main();
