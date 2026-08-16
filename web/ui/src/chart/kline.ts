import type { EChartsOption, SeriesOption } from 'echarts';
import type { ECharts } from 'echarts/core';
import {
  aggregateDaily,
  tfForDays,
  timeframeForVisibleDays,
  TF_LABEL,
  type Timeframe,
} from '../lib/aggregate';
import { MA_SPANS, sma, type MaSpan } from '../lib/dashboard';
import type { IndexBar } from '../lib/data-types';
import type { ThemePalette } from './theme';

export type RangeKey = 'all' | '5y' | '3y' | '1y' | 'custom';

export interface AggState {
  bars: IndexBar[];
  spans: Array<[number, number]>;
  tf: Timeframe;
  ma: Record<MaSpan, (number | null)[]>;
}

export function computeMaBySpan(closes: number[]): Record<MaSpan, (number | null)[]> {
  const result = {} as Record<MaSpan, (number | null)[]>;
  for (const span of MA_SPANS) result[span] = sma(closes, span);
  return result;
}

export function aggregate(daily: IndexBar[], tf: Timeframe): AggState {
  const a = aggregateDaily(daily, tf);
  return { bars: a.bars, spans: a.spans, tf, ma: computeMaBySpan(a.bars.map((b) => b.c)) };
}

export function dailyIndexForDate(daily: IndexBar[], dateStr: string, mode: 'gte' | 'lte'): number {
  if (mode === 'gte') {
    const i = daily.findIndex((b) => b.d >= dateStr);
    return i < 0 ? 0 : i;
  }
  for (let i = daily.length - 1; i >= 0; i--) if (daily[i].d <= dateStr) return i;
  return daily.length - 1;
}

export function buildSeries(
  agg: AggState,
  metaName: string,
  enabledMAs: Set<MaSpan>,
  p: ThemePalette,
): SeriesOption[] {
  const series: SeriesOption[] = [
    {
      id: 'candle',
      name: metaName,
      type: 'candlestick',
      data: agg.bars.map((b) => [b.o, b.c, b.l, b.h]),
      itemStyle: { color: p.up, color0: p.down, borderColor: p.up, borderColor0: p.down },
      z: 2,
    },
  ];
  for (const span of MA_SPANS) {
    if (!enabledMAs.has(span)) continue;
    series.push({
      id: `MA${span}`,
      name: `MA${span}`,
      type: 'line',
      data: agg.ma[span],
      smooth: true,
      showSymbol: false,
      connectNulls: false,
      lineStyle: { width: 1.4, color: p.ma[span] },
      itemStyle: { color: p.ma[span] },
      emphasis: { disabled: true },
      z: 3,
    });
  }
  return series;
}

export function buildOption(
  agg: AggState,
  metaName: string,
  enabledMAs: Set<MaSpan>,
  p: ThemePalette,
  zoom: { start: number; end: number },
): EChartsOption {
  return {
    backgroundColor: p.bg,
    animation: false,
    grid: { left: 72, right: 24, top: 20, bottom: 74 },
    xAxis: {
      type: 'category',
      data: agg.bars.map((b) => b.d),
      boundaryGap: true,
      axisLine: { lineStyle: { color: p.axisLine } },
      axisLabel: {
        color: p.dim,
        hideOverlap: true,
        formatter: (value: string) => {
          if (agg.tf === '1M') return value.slice(0, 7);
          if (agg.tf === '1Y') return value.slice(0, 4);
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
      { type: 'inside', start: zoom.start, end: zoom.end, zoomOnMouseWheel: true, moveOnMouseMove: true, moveOnMouseWheel: false },
      {
        type: 'slider', start: zoom.start, end: zoom.end, height: 24, bottom: 12,
        borderColor: p.border, backgroundColor: p.panel, fillerColor: 'rgba(79,142,247,0.16)',
        dataBackground: { lineStyle: { color: p.axisLine }, areaStyle: { color: p.panel } },
        selectedDataBackground: { lineStyle: { color: p.dim }, areaStyle: { color: p.splitLine } },
        handleStyle: { color: p.dim }, moveHandleStyle: { color: p.dim }, textStyle: { color: p.dim },
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
      formatter: makeTooltip(agg, metaName, enabledMAs, p),
    },
    series: buildSeries(agg, metaName, enabledMAs, p),
  };
}

function makeTooltip(
  agg: AggState,
  metaName: string,
  enabledMAs: Set<MaSpan>,
  p: ThemePalette,
): (params: unknown) => string {
  return (params: unknown) => {
    const list = params as Array<{ dataIndex: number; seriesType: string }>;
    const candle = list.find((x) => x.seriesType === 'candlestick');
    if (!candle) return '';
    const i = candle.dataIndex;
    const bar = agg.bars[i];
    if (!bar) return '';
    const prev = i > 0 ? agg.bars[i - 1].c : null;
    const chg = prev == null ? null : ((bar.c - prev) / prev) * 100;
    const chgColor = chg == null ? p.dim : chg >= 0 ? p.up : p.down;
    const chgStr = chg == null ? '—' : `${chg >= 0 ? '+' : ''}${chg.toFixed(2)}%`;

    const rows: string[] = [];
    rows.push(`<div style="font-weight:600;margin-bottom:4px">${bar.d} · ${metaName} · ${TF_LABEL[agg.tf]}</div>`);
    rows.push(`<div style="display:flex;gap:14px"><span>开 <b>${bar.o.toFixed(2)}</b></span><span>高 <b>${bar.h.toFixed(2)}</b></span></div>`);
    rows.push(`<div style="display:flex;gap:14px"><span>低 <b>${bar.l.toFixed(2)}</b></span><span>收 <b>${bar.c.toFixed(2)}</b></span></div>`);
    rows.push(`<div style="color:${chgColor}">涨跌幅 ${chgStr}</div>`);
    const maLines = MA_SPANS.filter((s) => enabledMAs.has(s))
      .map((s) => {
        const v = agg.ma[s][i];
        return v == null ? null : `<span style="color:${p.ma[s]}">MA${s} ${v.toFixed(2)}</span>`;
      })
      .filter((x): x is string => x != null);
    if (maLines.length > 0) {
      rows.push(`<div style="margin-top:4px;display:flex;gap:10px;flex-wrap:wrap">${maLines.join('')}</div>`);
    }
    return rows.join('');
  };
}

// ---------------------------------------------------------------- 控制器操作

export interface KLineCtrl {
  daily: IndexBar[];
  agg: AggState;
  enabledMAs: Set<MaSpan>;
  activeRange: RangeKey;
  programmatic: boolean;
}

function dispatchZoomPct(chart: ECharts, agg: AggState, sIdx: number, eIdx: number, ctrl: KLineCtrl): void {
  if (agg.bars.length <= 1) return;
  const n = agg.bars.length;
  const start = (Math.max(0, sIdx) / (n - 1)) * 100;
  const end = (Math.min(n - 1, eIdx) / (n - 1)) * 100;
  ctrl.programmatic = true;
  chart.dispatchAction({ type: 'dataZoom', start, end });
  ctrl.programmatic = false;
}

function zoomToDailyRange(chart: ECharts, agg: AggState, startDaily: number, endDaily: number, ctrl: KLineCtrl): void {
  const n = agg.bars.length;
  let sIdx = agg.spans.findIndex((sp) => sp[1] >= startDaily);
  if (sIdx < 0) sIdx = 0;
  let eIdx = -1;
  for (let i = 0; i < n; i++) if (agg.spans[i][0] <= endDaily) eIdx = i;
  if (eIdx < 0) eIdx = n - 1;
  dispatchZoomPct(chart, agg, sIdx, eIdx, ctrl);
}

function rebuildWithTimeframe(
  chart: ECharts, ctrl: KLineCtrl, tf: Timeframe, startDaily: number, endDaily: number,
  metaName: string, p: ThemePalette,
): void {
  ctrl.agg = aggregate(ctrl.daily, tf);
  chart.setOption(buildOption(ctrl.agg, metaName, ctrl.enabledMAs, p, { start: 0, end: 100 }), { notMerge: true });
  zoomToDailyRange(chart, ctrl.agg, startDaily, endDaily, ctrl);
}

function applyViewWindow(chart: ECharts, ctrl: KLineCtrl, fromDate: string, toDate: string, metaName: string, p: ThemePalette): void {
  const startDaily = dailyIndexForDate(ctrl.daily, fromDate, 'gte');
  const endDaily = dailyIndexForDate(ctrl.daily, toDate, 'lte');
  const tf = tfForDays(endDaily - startDaily + 1);
  if (tf === ctrl.agg.tf) zoomToDailyRange(chart, ctrl.agg, startDaily, endDaily, ctrl);
  else rebuildWithTimeframe(chart, ctrl, tf, startDaily, endDaily, metaName, p);
}

export function handleZoomChange(chart: ECharts, ctrl: KLineCtrl, metaName: string, p: ThemePalette): void {
  const opt = chart.getOption() as { dataZoom?: Array<{ start?: number; end?: number }> };
  const dz = opt.dataZoom;
  if (!dz || dz.length === 0) return;
  const n = ctrl.agg.bars.length;
  const firstIdx = Math.max(0, Math.min(n - 1, Math.floor(((dz[0].start ?? 0) / 100) * (n - 1))));
  const lastIdx = Math.max(0, Math.min(n - 1, Math.ceil(((dz[0].end ?? 100) / 100) * (n - 1))));
  const startDaily = ctrl.agg.spans[firstIdx][0];
  const endDaily = ctrl.agg.spans[lastIdx][1];
  const tf = timeframeForVisibleDays(endDaily - startDaily + 1, ctrl.agg.tf);
  if (tf !== ctrl.agg.tf) rebuildWithTimeframe(chart, ctrl, tf, startDaily, endDaily, metaName, p);
}

export function zoomRange(chart: ECharts, ctrl: KLineCtrl, range: RangeKey, metaName: string, p: ThemePalette): void {
  const lastDate = ctrl.daily[ctrl.daily.length - 1].d;
  let fromDate = ctrl.daily[0].d;
  if (range !== 'all') {
    const years = range === '5y' ? 5 : range === '3y' ? 3 : 1;
    const last = new Date(`${lastDate}T00:00:00Z`);
    const from = new Date(last);
    from.setUTCFullYear(from.getUTCFullYear() - years);
    fromDate = from.toISOString().slice(0, 10);
  }
  ctrl.programmatic = true;
  ctrl.activeRange = range;
  applyViewWindow(chart, ctrl, fromDate, lastDate, metaName, p);
  ctrl.programmatic = false;
}

export function setEnabledMAs(chart: ECharts, ctrl: KLineCtrl, set: Set<MaSpan>, metaName: string, p: ThemePalette): void {
  ctrl.enabledMAs = set;
  chart.setOption({ series: buildSeries(ctrl.agg, metaName, ctrl.enabledMAs, p) });
}

/** 初始化/重置视图：聚合回日K + 近一年窗口。 */
export function initView(chart: ECharts, ctrl: KLineCtrl, metaName: string, p: ThemePalette): void {
  ctrl.agg = aggregate(ctrl.daily, '1D');
  ctrl.activeRange = '1y';
  chart.setOption(buildOption(ctrl.agg, metaName, ctrl.enabledMAs, p, { start: 0, end: 100 }), { notMerge: true });
  const lastDate = ctrl.daily[ctrl.daily.length - 1].d;
  const from = new Date(`${lastDate}T00:00:00Z`);
  from.setUTCFullYear(from.getUTCFullYear() - 1);
  ctrl.programmatic = true;
  applyViewWindow(chart, ctrl, from.toISOString().slice(0, 10), lastDate, metaName, p);
  ctrl.programmatic = false;
}

/** 主题切换：仅按新配色重建，保留当前缩放窗口。 */
export function rebuildTheme(chart: ECharts, ctrl: KLineCtrl, metaName: string, p: ThemePalette): void {
  const opt = chart.getOption() as { dataZoom?: Array<{ start?: number; end?: number }> };
  const dz = opt.dataZoom;
  const start = dz && dz.length ? dz[0].start ?? 0 : 0;
  const end = dz && dz.length ? dz[0].end ?? 100 : 100;
  chart.setOption(buildOption(ctrl.agg, metaName, ctrl.enabledMAs, p, { start, end }), { notMerge: true });
}
