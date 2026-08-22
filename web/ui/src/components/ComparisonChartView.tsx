import { useEffect, useRef } from 'react';
import * as echarts from 'echarts';
import type { ComparisonData, ComparisonRun } from '../api/research';
import type { AppTheme } from '../chart/theme';
import { pal } from '../chart/theme';

/** 双序列归一化对照图（原静态站 market-comparison 的 ECharts 版）。 */
export function ComparisonChartView({ data, theme }: { data: ComparisonData; theme: AppTheme }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const chart = echarts.init(el);
    const p = pal(theme);
    const dates = data.data.map((row) => row[0]);
    const src = data.data.map((row) => row[1]);
    const tgt = data.data.map((row) => row[2]);
    const signalPoints = data.dailyMappingSignals
      .map((s) => {
        const idx = dates.indexOf(s.targetDate);
        if (idx < 0) return null;
        return {
          coord: [s.targetDate, tgt[idx]],
          value: `${s.direction === 'up' ? '+' : ''}${s.change}%`,
          itemStyle: {
            color: s.direction === 'up' ? p.up : p.down,
            borderColor: p.bg,
            borderWidth: 1,
          },
        };
      })
      .filter((x): x is NonNullable<typeof x> => x !== null);

    const runAreas = (runs: ComparisonRun[], color: string) =>
      runs.map((r) => ({
        name: r.start,
        xAxis: r.start,
        xAxis1: r.end,
        itemStyle: { color, opacity: 0.12 },
      }));

    chart.setOption(
      {
        backgroundColor: 'transparent',
        animation: false,
        textStyle: { fontFamily: 'Menlo, Monaco, "SF Mono", monospace' },
        title: { text: data.title, left: 8, top: 6, textStyle: { fontSize: 14, fontWeight: 700, color: p.text } },
        legend: {
          top: 32,
          left: 8,
          data: [data.source.label, data.target.label, '信号'],
          textStyle: { color: p.dim, fontSize: 11 },
        },
        tooltip: {
          trigger: 'axis',
          backgroundColor: p.panel,
          borderColor: p.border,
          textStyle: { color: p.text, fontSize: 12 },
        },
        grid: { left: 64, right: 24, top: 72, bottom: 56 },
        xAxis: {
          type: 'category',
          data: dates,
          axisLine: { lineStyle: { color: p.border } },
          axisLabel: { color: p.dim, fontSize: 11 },
        },
        yAxis: {
          type: 'value',
          scale: true,
          name: '归一化 100',
          nameTextStyle: { color: p.dim, fontSize: 11 },
          axisLine: { lineStyle: { color: p.border } },
          axisLabel: { color: p.dim, fontSize: 11 },
          splitLine: { lineStyle: { color: p.border, opacity: 0.4 } },
        },
        dataZoom: [{ type: 'inside' }, { type: 'slider', height: 18, bottom: 8, borderColor: p.border }],
        series: [
          {
            name: data.source.label,
            type: 'line',
            data: src,
            showSymbol: false,
            lineStyle: { width: 1.6, color: p.ma['20'] },
            markArea: {
              silent: true,
              data: [...runAreas(data.upRuns, p.up), ...runAreas(data.downRuns, p.down)],
            },
          },
          {
            name: data.target.label,
            type: 'line',
            data: tgt,
            showSymbol: false,
            lineStyle: { width: 1.6, color: p.ma['60'] },
          },
          {
            name: '信号',
            type: 'scatter',
            data: signalPoints,
            symbolSize: 8,
            symbol: 'pin',
            label: { show: true, position: 'top', fontSize: 10, color: p.dim },
          },
        ],
      },
      true,
    );
    const onResize = () => chart.resize();
    window.addEventListener('resize', onResize);
    return () => {
      window.removeEventListener('resize', onResize);
      chart.dispose();
    };
  }, [data, theme]);

  return (
    <div className="page-view">
      <div ref={ref} style={{ width: '100%', height: 460 }} />
      <p className="notice-text">
        数据区间 {data.startDate} 至 {data.endDate}（{data.tradingDays} 个共同交易日）。源（
        {data.source.symbol}）与目标（{data.target.symbol}）按首日归一化为 100。高亮区 = 源连涨/连跌
        ≥{data.consecutiveMove.days} 日；图钉 = 源单日变动 ±{data.dailyMappingPct}% 投影到下一个目标交易日。
        用于历史对照，不构成交易信号或投资建议。
      </p>
    </div>
  );
}
