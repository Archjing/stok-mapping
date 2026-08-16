import { useCallback, useEffect, useRef } from 'react';
import * as echarts from 'echarts/core';
import { CandlestickChart, LineChart } from 'echarts/charts';
import {
  DataZoomComponent,
  GridComponent,
  TooltipComponent,
} from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
import type { ECharts } from 'echarts/core';

echarts.use([
  CandlestickChart,
  LineChart,
  GridComponent,
  TooltipComponent,
  DataZoomComponent,
  CanvasRenderer,
]);

/** 管理单个 ECharts 实例的生命周期（init/resize/dispose）。 */
export function useECharts() {
  const ref = useRef<HTMLDivElement>(null);
  const chartRef = useRef<ECharts | null>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    chartRef.current = echarts.init(el);
    const onResize = () => chartRef.current?.resize();
    window.addEventListener('resize', onResize);
    return () => {
      window.removeEventListener('resize', onResize);
      chartRef.current?.dispose();
      chartRef.current = null;
    };
  }, []);

  // 稳定引用：避免依赖此 getter 的 effect 每次渲染都重跑
  const getChart = useCallback(() => chartRef.current, []);

  return { ref, chart: getChart };
}
