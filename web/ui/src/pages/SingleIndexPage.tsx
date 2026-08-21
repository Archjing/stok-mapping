import { useCallback, useEffect, useRef, useState } from 'react';
import { KLineChart } from '../components/KLineChart';
import { fetchBars } from '../api/market';
import type { Market } from '../api/market';
import { useTheme } from '../components/ThemeContext';
import type { IndexBar } from '../lib/data-types';

interface SymbolName { symbol: string; name: string; }

function todayStr(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

/**
 * 单标的看板（A股 / 美股 共用）。
 *
 * props 决定市场与预设指数池：
 *   market      -> fetchBars 的 market 参数（'cn' | 'us'）
 *   indices     -> 预设指数 chip（指数切换 + KLineChart 内搜索候选）
 *   initialSymbol/initialName -> 首屏默认标的
 *
 * 行为（与原 MarketChartPage 一致）：
 *   - 首屏近一年先行渲染，再后台拉全量补全；
 *   - 15:05 后每分钟轮询预设核心指数，数据日期变化才更新，全部到今日后停止；
 *   - 指数 chip 点击切换（指数始终在池内）；个股搜索新增。
 */
export function SingleIndexPage({
  market,
  indices,
  coreSymbols,
  initialSymbol,
  initialName,
  marketLabel,
}: {
  market: Market;
  indices: ReadonlyArray<SymbolName>;
  /** 预设里的“核心指数”（用于盘后轮询，通常不含自定义恐慌指数）。 */
  coreSymbols: ReadonlyArray<string>;
  initialSymbol: string;
  initialName: string;
  marketLabel: string;
}) {
  const [symbol, setSymbol] = useState(initialSymbol);
  const [name, setName] = useState(initialName);
  const [bars, setBars] = useState<IndexBar[]>([]);
  const [error, setError] = useState('');
  const [autoRefresh, setAutoRefresh] = useState('');
  const theme = useTheme();

  const lastBarDateRef = useRef(bars.length ? bars[bars.length - 1].d : '');
  lastBarDateRef.current = bars.length ? bars[bars.length - 1].d : '';

  // 盘后轮询：预设核心指数数据日期变化才更新，全部到今日后停止
  useEffect(() => {
    if (!coreSymbols.length) return;
    let stopped = false;
    const tick = async () => {
      if (stopped) return;
      const now = new Date();
      if (now.getHours() < 15 || (now.getHours() === 15 && now.getMinutes() < 5)) return;
      // 只轮询预设核心指数；用户搜索切到的非核心个股不进入盘后轮询
      if (!coreSymbols.includes(symbol)) return;
      try {
        const recent = await fetchBars(symbol, { recent: '1y' }, market);
        const newLast = recent.length ? recent[recent.length - 1].d : '';
        if (newLast && newLast !== lastBarDateRef.current) {
          const full = await fetchBars(symbol, {}, market);
          if (full.length && full[full.length - 1].d !== lastBarDateRef.current) {
            setBars(full);
            lastBarDateRef.current = full[full.length - 1].d;
            setAutoRefresh(`✓ ${now.toLocaleTimeString()} 已自动更新（数据日期 ${lastBarDateRef.current}）`);
          }
        }
        if (lastBarDateRef.current >= todayStr(now)) stopped = true;
      } catch {
        /* 轮询失败静默，下个 tick 再试 */
      }
    };
    tick();
    const id = window.setInterval(tick, 60_000);
    return () => window.clearInterval(id);
  }, [symbol, market, coreSymbols]);

  // 数据加载：近一年先行，再补全量
  useEffect(() => {
    let alive = true;
    setBars([]);
    setError('');
    (async () => {
      try {
        const recent = await fetchBars(symbol, { recent: '1y' }, market);
        if (!alive) return;
        setBars(recent);
        const full = await fetchBars(symbol, {}, market);
        if (!alive) return;
        setBars(full);
      } catch (e) {
        if (alive) setError(`行情加载失败：${e}`);
      }
    })();
    return () => {
      alive = false;
    };
  }, [symbol, market]);

  const onSelectSymbol = useCallback((s: string, n?: string) => {
    setSymbol(s);
    if (n) setName(n);
  }, []);

  return (
    <div className="page-view">
      {error && <p className="error">{error}</p>}
      <div className="view-head">
        <div className="view-title">
          <span className="view-market-tag">{marketLabel}</span>
          <h2 className="view-name">{name}<span className="view-code">{symbol}</span></h2>
        </div>
      </div>

      {bars.length > 0 && (
        <KLineChart
          key={`${market}-${symbol}`}
          symbol={symbol}
          name={name}
          bars={bars}
          theme={theme}
          indices={indices}
          market={market}
          onSelectSymbol={onSelectSymbol}
        />
      )}

      <footer className="status">
        {bars.length > 0
          ? `${name} ${symbol}：${bars[0].d} ~ ${bars[bars.length - 1].d}（${bars.length} 根日线）`
          : ''}{' '}
        · 滚轮缩放 / 拖拽平移 / 双击复位
        {autoRefresh && <span className="auto-refresh">{autoRefresh}</span>}
      </footer>
    </div>
  );
}
