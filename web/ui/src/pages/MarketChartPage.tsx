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
  const [autoRefresh, setAutoRefresh] = useState('');

  // 单指数视图：每日 15:05 后自动轮询核心指数，有新数据才更新
  // 每分钟 tick 检查一次（避免长间隔 setInterval 漂移），每个自然日只检查一次
  useEffect(() => {
    if (view !== 'single') return;
    if (!CORE_INDICES.some((i) => i.symbol === symbol)) return;
    let lastCheckedDate = '';
    let lastBarDate = bars.length ? bars[bars.length - 1].d : '';
    const tick = async () => {
      const now = new Date();
      if (now.getHours() < 15 || (now.getHours() === 15 && now.getMinutes() < 5)) return;
      const today = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
      if (lastCheckedDate === today) return;
      lastCheckedDate = today; // 无论有无新数据，当天只查一次
      try {
        const recent = await fetchBars(symbol, { recent: '1y' });
        const newLast = recent.length ? recent[recent.length - 1].d : '';
        if (newLast && newLast !== lastBarDate) {
          const full = await fetchBars(symbol);
          if (full.length && full[full.length - 1].d !== lastBarDate) {
            setBars(full);
            lastBarDate = full[full.length - 1].d;
            setAutoRefresh(`✓ ${now.toLocaleTimeString()} 已自动更新（15:05 轮询）`);
          }
        }
      } catch {
        /* 轮询失败静默，明天再试 */
      }
    };
    tick();
    const id = window.setInterval(tick, 60_000);
    return () => window.clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view, symbol]);

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
          {autoRefresh && <span className="auto-refresh">{autoRefresh}</span>}
        </footer>
      )}
    </div>
  );
}
