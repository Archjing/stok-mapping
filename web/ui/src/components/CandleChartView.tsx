import { useEffect, useRef } from 'react';
import * as echarts from 'echarts';
import type { CandleData } from '../api/research';
import type { AppTheme } from '../chart/theme';
import { pal } from '../chart/theme';

/** 双蜡烛对照图（ECharts candlestick，source 左轴 / target 右轴，独立价格尺度）。 */
export function CandleChartView({ data, theme }: { data: CandleData; theme: AppTheme }) {
  const ref = useRef<HTMLDivElement>(null);
  const p = pal(theme);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const chart = echarts.init(el);
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
          data: [
            { name: `${data.source.label}（橙涨/蓝跌）`, itemStyle: { color: p.soxUp } },
            { name: `${data.target.label}（红涨/绿跌）`, itemStyle: { color: p.up } },
          ],
          textStyle: { color: p.dim, fontSize: 11 },
        },
        tooltip: {
          trigger: 'axis',
          axisPointer: { type: 'cross' },
          backgroundColor: p.panel,
          borderColor: p.border,
          textStyle: { color: p.text, fontSize: 12 },
          formatter: function (params: any) {
            // 复刻 ECharts 默认蜡烛 tooltip：日期标题 + 每个标的区块（名称行 + OHLC 四行）。
            // 名称行右侧追加当日涨跌幅，标准单日口径：(今收 - 昨收) / 昨收。
            // 颜色统一用 item.color（ECharts 按内部 sign 判定选好的蜡烛填充色），
            // 保证名称圆点 / OHLC 小圆点 / 涨跌幅数字与图上 bar 实体颜色完全一致。
            var axisLabel = params.length
              ? params[0].axisValueLabel || params[0].axisValue
              : '';
            var nameStyle = 'font-size:12px;color:' + p.text + ';font-weight:400';
            var valueStyle = 'font-size:14px;color:' + p.text + ';font-weight:900';
            var gap = 'margin:10px 0 0;line-height:1;';
            var dims = [
              { name: 'open' },
              { name: 'close' },
              { name: 'lowest' },
              { name: 'highest' },
            ];
            function fmt(v: number) {
              return v.toLocaleString('en-US', { maximumFractionDigits: 20 });
            }
            var html =
              '<div style="margin:0;line-height:1;">' +
              '<div style="' + nameStyle + ';line-height:1;">' + axisLabel + '</div>' +
              params
                .map(function (item: any) {
                  var dataArr = item.data; // [open, close, lowest, highest]（ECharts 顺序）
                  var open = dataArr[0];
                  var close = dataArr[1];
                  var lowest = dataArr[2];
                  var highest = dataArr[3];
                  var isSource = item.seriesName === data.source.label;
                  // 标准单日涨跌幅：(今收 - 昨收) / 昨收
                  var raw = isSource ? data.source.data : data.target.data; // [open, high, low, close]
                  var idx = item.dataIndex;
                  var prevClose = idx > 0 ? Number(raw[idx - 1][3]) : NaN;
                  var hasPrev = !isNaN(prevClose) && prevClose > 0;
                  var pct = hasPrev ? ((close - prevClose) / prevClose) * 100 : NaN;
                  var color = item.color || p.text;
                  var bigMarker =
                    '<span style="display:inline-block;margin-right:4px;border-radius:10px;width:10px;height:10px;background-color:' +
                    color +
                    ';"></span>';
                  var subMarker =
                    '<span style="display:inline-block;vertical-align:middle;margin-right:8px;margin-left:3px;border-radius:4px;width:4px;height:4px;background-color:' +
                    color +
                    ';"></span>';
                  var ohlc = [open, close, lowest, highest];
                  var subRows = ohlc
                    .map(function (v, i) {
                      return (
                        '<div style="' + gap + '">' +
                        subMarker +
                        '<span style="' + nameStyle + ';margin-left:2px">' + dims[i].name + '</span>' +
                        '<span style="float:right;margin-left:20px;' + valueStyle + '">' + fmt(v) + '</span>' +
                        '<div style="clear:both"></div>' +
                        '</div>'
                      );
                    })
                    .join('');
                  return (
                    '<div style="' + gap + '">' +
                    bigMarker +
                    '<span style="' + nameStyle + ';margin-left:2px">' + item.seriesName + '</span>' +
                    '<span style="float:right;margin-left:20px;color:' + color + ';' + valueStyle + '">' +
                    (hasPrev ? pct.toFixed(2) + '%' : '—') +
                    '</span>' +
                    '<div style="clear:both"></div>' +
                    subRows +
                    '</div>'
                  );
                })
                .join('') +
              '</div>';
            return html;
          },
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
              color: p.soxUp,
              color0: p.soxDown,
              borderColor: p.soxUp,
              borderColor0: p.soxDown,
            },
          },
          {
            name: data.target.label,
            type: 'candlestick',
            data: toECharts(data.target.data),
            yAxisIndex: 1,
            itemStyle: {
              color: p.up,
              color0: p.down,
              borderColor: p.up,
              borderColor0: p.down,
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
        蜡烛对照：{data.source.label}（左轴，
        <b style={{ color: p.soxUp }}>橙涨</b>/<b style={{ color: p.soxDown }}>蓝跌</b>）与 {data.target.label}（右轴，
        <b style={{ color: p.up }}>红涨</b>/<b style={{ color: p.down }}>绿跌</b>）。共同交易日{' '}
        {data.startDate} 至 {data.endDate}，按各自价位独立缩放。阳线 = 收 &gt; 开，阴线 = 收 &lt; 开。
      </p>
    </div>
  );
}
