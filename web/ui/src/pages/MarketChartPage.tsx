import { useCallback, useEffect, useState } from 'react';
import { KLineChart } from '../components/KLineChart';
import { fetchBars, fetchInstruments, type Instrument } from '../api/market';
import type { Theme } from '../chart/theme';

function initialTheme(): Theme {
  try {
    return (localStorage.getItem('index-chart-theme') as Theme) || 'dark';
  } catch {
    return 'dark';
  }
}

export function MarketChartPage() {
  const [instruments, setInstruments] = useState<Instrument[]>([]);
  const [symbol, setSymbol] = useState('SH.000001');
  const [bars, setBars] = useState<Array<{ d: string; o: number; h: number; l: number; c: number }>>([]);
  const [error, setError] = useState('');
  const [theme, setTheme] = useState<Theme>(initialTheme);

  useEffect(() => {
    fetchInstruments()
      .then((items) => {
        setInstruments(items);
        if (items.length > 0 && !items.some((i) => i.symbol === 'SH.000001')) {
          setSymbol(items[0].symbol);
        }
      })
      .catch((e) => setError(`指数列表加载失败：${e}`));
  }, []);

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

  const meta = instruments.find((i) => i.symbol === symbol);

  return (
    <div className="page" data-theme={theme}>
      <header className="toolbar">
        <div className="brand">
          <h1>stok-mapping 网站控制台</h1>
          <p>A股指数走势 · 对照看板（P1b 待接入）</p>
        </div>
        <div className="toolbar-right">
          <div className="seg">
            {instruments.map((i) => (
              <button
                key={i.symbol}
                className={i.symbol === symbol ? 'active' : ''}
                onClick={() => setSymbol(i.symbol)}
              >
                {i.name}
              </button>
            ))}
          </div>
          <button className="icon-btn" onClick={toggleTheme} title="切换明暗主题">
            {theme === 'dark' ? '☀️' : '🌙'}
          </button>
        </div>
      </header>

      {error && <p className="error">{error}</p>}

      {bars.length > 0 && (
        <KLineChart symbol={symbol} name={meta?.name ?? symbol} bars={bars} theme={theme} />
      )}

      <footer className="status">
        {meta ? `${meta.name} ${meta.symbol}：${meta.start} ~ ${meta.end}（${meta.count} 根日线）` : ''} · 滚轮缩放 / 拖拽平移 / 双击复位
      </footer>
    </div>
  );
}
