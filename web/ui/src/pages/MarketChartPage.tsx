import { useCallback, useEffect, useState } from 'react';
import { KLineChart } from '../components/KLineChart';
import { fetchBars } from '../api/market';
import type { Theme } from '../chart/theme';

/** 核心指数切换器（固定 4 个；全量指数检索由后续 search 提供） */
const CORE_INDICES = [
  { symbol: 'SH.000001', name: '上证指数' },
  { symbol: 'SZ.399001', name: '深证成指' },
  { symbol: 'SH.000300', name: '沪深300' },
  { symbol: 'SZ.399006', name: '创业板指' },
] as const;

interface Bar {
  d: string;
  o: number;
  h: number;
  l: number;
  c: number;
}

function initialTheme(): Theme {
  try {
    return (localStorage.getItem('index-chart-theme') as Theme) || 'dark';
  } catch {
    return 'dark';
  }
}

// 主题要挂到 <html>，这样 body 最外层背景色（var(--bg)）才能随主题生效
function applyRootTheme(t: Theme): void {
  document.documentElement.dataset.theme = t;
}

applyRootTheme(initialTheme());

export function MarketChartPage() {
  const [symbol, setSymbol] = useState('SH.000001');
  const [bars, setBars] = useState<Bar[]>([]);
  const [error, setError] = useState('');
  const [theme, setTheme] = useState<Theme>(initialTheme);

  useEffect(() => {
    applyRootTheme(theme);
  }, [theme]);

  useEffect(() => {
    setBars([]);
    fetchBars(symbol)
      .then(setBars)
      .catch((e) => setError(`行情加载失败：${e}`));
  }, [symbol]);

  const toggleTheme = useCallback(() => {
    setTheme((t) => {
      const next = t === 'dark' ? 'light' : 'dark';
      try {
        localStorage.setItem('index-chart-theme', next);
      } catch {
        /* ignore */
      }
      return next;
    });
  }, []);

  const meta = CORE_INDICES.find((i) => i.symbol === symbol);

  return (
    <div className="page" data-theme={theme}>
      <header className="toolbar">
        <div className="brand">
          <h1>stok-mapping 网站控制台</h1>
          <p>A股指数走势 · 对照看板（P1b 待接入）</p>
        </div>
        <button className="icon-btn" onClick={toggleTheme} title="切换明暗主题">
          {theme === 'dark' ? '☀️' : '🌙'}
        </button>
      </header>

      {error && <p className="error">{error}</p>}

      {bars.length > 0 && (
        <KLineChart
          symbol={symbol}
          name={meta?.name ?? symbol}
          bars={bars}
          theme={theme}
          indices={CORE_INDICES}
          onSelectSymbol={setSymbol}
        />
      )}

      <footer className="status">
        {bars.length > 0
          ? `${meta?.name ?? symbol} ${symbol}：${bars[0].d} ~ ${bars[bars.length - 1].d}（${bars.length} 根日线）`
          : ''} · 滚轮缩放 / 拖拽平移 / 双击复位
      </footer>
    </div>
  );
}
