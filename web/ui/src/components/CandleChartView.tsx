import { useEffect, useRef } from 'react';
import * as echarts from 'echarts';
import type { CandleData } from '../api/research';
import type { AppTheme } from '../chart/theme';
import { pal } from '../chart/theme';

/** 双蜡烛对照图（ECharts candlestick，source 左轴 / target 右轴，独立价格尺度）。 */
export function CandleChartView({ data, theme }: { data: CandleData; theme: AppTheme }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const chart = echarts.init(el);
    const p = pal(theme);
    // ECharts candlestick 序列顺序：[open, close, low, high]；后端给的是 [open, high, low, close]
    const toECharts = (rows: number[][]) => rows.map((r) => [r[0], r[3], r[2], r[1]]);

    chart.setOption(
      {
        backgroundColor: 'transparent',
        animation: false,
        textStyle: { fontFamily: 'Menlo, Monaco, "SF Mono", monospace' },
        legend: {
          top: 8,
          left: 8,
          data: [data.source.label, data.target.label],
          textStyle: { color: p.dim, fontSize: 11 },
        },
        tooltip: {
          trigger: 'axis',
          axisPointer: { type: 'cross' },
          backgroundColor: p.panel,
          borderColor: p.border,
          textStyle: { color: p.text, fontSize: 12 },
        },
        grid: { left: 66, right: 70, top: 40, bottom: 64 },
        xAxis: {
          type: 'category',
          data: data.dates,
          axisLine: { lineStyle: { color: p.border } },
          axisLabel: { color: p.dim, fontSize: 11 },
        },
        yAxis: [
          {
            type: 'value',
            scale: true,
            name: data.source.label,
            nameTextStyle: { color: p.dim, fontSize: 11 },
            axisLine: { lineStyle: { color: p.border } },
            axisLabel: { color: p.dim, fontSize: 11 },
            splitLine: { lineStyle: { color: p.border, opacity: 0.4 } },
          },
          {
            type: 'value',
            scale: true,
            name: data.target.label,
            position: 'right',
            nameTextStyle: { color: p.dim, fontSize: 11 },
            axisLine: { lineStyle: { color: p.border } },
            axisLabel: { color: p.dim, fontSize: 11 },
            splitLine: { show: false },
          },
        ],
        dataZoom: [{ type: 'inside' }, { type: 'slider', height: 16, bottom: 6, borderColor: p.border }],
        series: [
          {
            name: data.source.label,
            type: 'candlestick',
            data: toECharts(data.source.data),
            yAxisIndex: 0,
            itemStyle: {
              color: p.up,
              color0: p.down,
              borderColor: p.up,
              borderColor0: p.down,
            },
          },
          {
            name: data.target.label,
            type: 'candlestick',
            data: toECharts(data.target.data),
            yAxisIndex: 1,
            itemStyle: {
              color: 'rgba(0,0,0,0)',
              color0: 'rgba(0,0,0,0)',
              borderColor: p.down,
              borderColor0: p.down,
              borderWidth: 1,
            },
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
      <div ref={ref} style={{ width: '100%', height: 520 }} />
      <p className="notice-text">
        蜡烛对照：{data.source.label}（左轴）与 {data.target.label}（右轴），共同交易日 {data.startDate} 至{' '}
        {data.endDate}，按各自价位独立缩放。涨红跌绿口径与行情一致。
      </p>
    </div>
  );
}
