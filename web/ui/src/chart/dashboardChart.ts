import type { EChartsOption } from 'echarts';
import type { ECharts } from 'echarts/core';
import {
  NORM_AXIS_PCT,
  buildBarMaps,
  buildDashSeries,
  buildSharedDates,
  dashTooltipHtml,
  dashWindowFromPct,
  type DashInstrument,
  type DashMode,
  type MaSpan,
  type Normalization,
} from '../lib/dashboard';
import type { IndexBar } from '../lib/data-types';
import { CHART_FONT, type ThemePalette } from './theme';

export type DashRangeKey = 'all' | '5y' | '3y' | '1y' | 'custom';

export interface DashCtrl {
  insts: DashInstrument[];
  dates: string[];
  barMaps: Array<Map<string, IndexBar>>;
  zoom: { start: number; end: number };
  norm: Normalization;
  mode: DashMode;
  maSpan: MaSpan;
  programmatic: boolean;
}

export function makeDashCtrl(insts: DashInstrument[]): DashCtrl {
  const dates = buildSharedDates(insts);
  return {
    insts,
    dates,
    barMaps: buildBarMaps(insts),
    zoom: defaultDashZoom(dates),
    norm: 'window',
    mode: 'close',
    maSpan: 20,
    programmatic: false,
  };
}

export function defaultDashZoom(dates: string[]): { start: number; end: number } {
  const n = dates.length - 1;
  if (n <= 0) return { start: 0, end: 100 };
  const lastDate = dates[dates.length - 1];
  const from = new Date(`${lastDate}T00:00:00Z`);
  from.setUTCFullYear(from.getUTCFullYear() - 3);
  const fromStr = from.toISOString().slice(0, 10);
  const idx = Math.max(0, dates.findIndex((d) => d >= fromStr));
  return { start: (idx / n) * 100, end: 100 };
}

export function buildDashOption(
  ctrl: DashCtrl,
  p: ThemePalette,
  colors: ReadonlyMap<string, string>,
): EChartsOption {
  const win = dashWindowFromPct(ctrl.dates, ctrl.zoom.start, ctrl.zoom.end);
  const windowStart = ctrl.dates[win.startIdx];
  const windowEnd = ctrl.dates[win.endIdx];
  return {
    backgroundColor: p.bg,
    animation: false,
    textStyle: { fontFamily: CHART_FONT },
    grid: { left: 72, right: 24, top: 20, bottom: 74 },
    xAxis: {
      type: 'category',
      data: ctrl.dates,
      boundaryGap: true,
      axisLine: { lineStyle: { color: p.axisLine } },
      axisLabel: { color: p.dim, formatter: (v: string) => v.slice(0, 7) },
      axisTick: { show: false },
      splitLine: { show: false },
      min: 'dataMin',
      max: 'dataMax',
    },
    yAxis: {
      scale: true,
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: {
        color: p.dim,
        formatter: (v: number) => (NORM_AXIS_PCT[ctrl.norm] ? `${v}%` : String(v)),
      },
      splitLine: { lineStyle: { color: p.splitLine } },
    },
    dataZoom: [
      { type: 'inside', start: ctrl.zoom.start, end: ctrl.zoom.end, zoomOnMouseWheel: true, moveOnMouseMove: true, moveOnMouseWheel: false },
      {
        type: 'slider', start: ctrl.zoom.start, end: ctrl.zoom.end, height: 24, bottom: 12,
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
      formatter: (params: unknown) => dashTooltipParams(ctrl, p, colors, params),
    },
    series: buildDashSeries(ctrl.insts, ctrl.dates, {
      mode: ctrl.mode,
      maSpan: ctrl.maSpan,
      norm: ctrl.norm,
      windowStart,
      windowEnd,
      colors,
    }),
  };
}

function dashTooltipParams(
  ctrl: DashCtrl,
  p: ThemePalette,
  colors: ReadonlyMap<string, string>,
  params: unknown,
): string {
  const list = params as Array<{ dataIndex: number }>;
  if (!list.length || ctrl.dates.length === 0) return '';
  const i = list[0].dataIndex;
  const win = dashWindowFromPct(ctrl.dates, ctrl.zoom.start, ctrl.zoom.end);
  return dashTooltipHtml(
    ctrl.insts,
    ctrl.barMaps,
    ctrl.dates,
    i,
    ctrl.dates[win.startIdx],
    ctrl.dates[win.endIdx],
    ctrl.norm,
    colors,
    { text: p.text, dim: p.dim, up: p.up, down: p.down },
  );
}

/** 仅在缩放/平移后重建 series（保留 dataZoom 位置）。 */
export function rebuildDashSeries(
  chart: ECharts,
  ctrl: DashCtrl,
  colors: ReadonlyMap<string, string>,
): void {
  const win = dashWindowFromPct(ctrl.dates, ctrl.zoom.start, ctrl.zoom.end);
  chart.setOption({
    series: buildDashSeries(ctrl.insts, ctrl.dates, {
      mode: ctrl.mode,
      maSpan: ctrl.maSpan,
      norm: ctrl.norm,
      windowStart: ctrl.dates[win.startIdx],
      windowEnd: ctrl.dates[win.endIdx],
      colors,
    }),
  });
}

export function dashZoomRange(
  chart: ECharts,
  ctrl: DashCtrl,
  range: DashRangeKey,
  colors: ReadonlyMap<string, string>,
): void {
  if (range === 'custom') return;
  const lastDate = ctrl.dates[ctrl.dates.length - 1];
  let startPct = 0;
  if (range !== 'all') {
    const years = range === '5y' ? 5 : range === '3y' ? 3 : 1;
    const from = new Date(`${lastDate}T00:00:00Z`);
    from.setUTCFullYear(from.getUTCFullYear() - years);
    const idx = Math.max(0, ctrl.dates.findIndex((d) => d >= from.toISOString().slice(0, 10)));
    const n = ctrl.dates.length - 1;
    startPct = (idx / n) * 100;
  }
  ctrl.zoom = { start: startPct, end: 100 };
  ctrl.programmatic = true;
  chart.dispatchAction({ type: 'dataZoom', start: startPct, end: 100 });
  ctrl.programmatic = false;
  rebuildDashSeries(chart, ctrl, colors);
}
