import { useCallback, useEffect, useState } from 'react';
import { KLineChart } from '../components/KLineChart';
import { ComparisonDashboard } from '../components/ComparisonDashboard';
import { fetchBars } from '../api/market';
import type { Theme } from '../chart/theme';
import { CORE_INDICES } from '../lib/instruments';

interface Bar {
  d: string;
  o: number;
  h: number;
  l: number;
  c: number;
}

type ViewMode = 'single' | 'dash';

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
  const [view, setView] = useState<ViewMode>('single');
  const [symbol, setSymbol] = useState('SH.000001');
  const [name, setName] = useState('上证指数');
  const [bars, setBars] = useState<Bar[]>([]);
  const [error, setError] = useState('');
  const [theme, setTheme] = useState<Theme>(initialTheme);

  useEffect(() => {
    applyRootTheme(theme);
  }, [theme]);

  useEffect(() => {
    let alive = true;
    setBars([]);
    (async () => {
      try {
        const recent = await fetchBars(symbol, { recent: '1y' });
        if (!alive) return;
        setBars(recent);
        const full = await fetchBars(symbol);
        if (!alive) return;
        setBars(full);
      } catch (e) {
        if (alive) setError(`行情加载失败：${e}`);
      }
    })();
    return () => {
      alive = false;
    };
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

  const onSelectSymbol = useCallback((s: string, n?: string) => {
    setSymbol(s);
    if (n) setName(n);
  }, []);

  return (
    <div className="page" data-theme={theme}>
      <header className="toolbar">
        <div className="brand">
          <h1>stok-mapping 网站控制台</h1>
          <p>A股指数 / 个股走势 · 归一化对照看板</p>
        </div>
        <div className="toolbar-right">
          <div className="seg">
            <button className={view === 'single' ? 'active' : ''} onClick={() => setView('single')}>
              单标的
            </button>
            <button className={view === 'dash' ? 'active' : ''} onClick={() => setView('dash')}>
              对照看板
            </button>
          </div>
          <button className="icon-btn" onClick={toggleTheme} title="切换明暗主题">
            {theme === 'dark' ? '☀️' : '🌙'}
          </button>
        </div>
      </header>

      {error && <p className="error">{error}</p>}

      {view === 'single' ? (
        bars.length > 0 && (
          <KLineChart
            symbol={symbol}
            name={name}
            bars={bars}
            theme={theme}
            indices={CORE_INDICES}
            onSelectSymbol={onSelectSymbol}
          />
        )
      ) : (
        <ComparisonDashboard theme={theme} />
      )}

      {view === 'single' && (
        <footer className="status">
          {bars.length > 0
            ? `${name} ${symbol}：${bars[0].d} ~ ${bars[bars.length - 1].d}（${bars.length} 根日线）`
            : ''}{' '}
          · 滚轮缩放 / 拖拽平移 / 双击复位
        </footer>
      )}
    </div>
  );
}
