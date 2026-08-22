import { Link, NavLink, Outlet, useNavigation } from 'react-router-dom';
import { useEffect, useState } from 'react';
import type { AppTheme } from '../chart/theme';
import { ThemeContext, applyRootTheme, loadTheme, saveTheme } from './ThemeContext';

/** 导航项：label + 目标路由。首页也带同一导航栏。 */
const NAV: Array<{ to: string; label: string }> = [
  { to: '/', label: '首页' },
  { to: '/market/cn', label: 'A股单标的' },
  { to: '/market/dash', label: 'A股对照' },
  { to: '/market/us', label: '美股单标的' },
];

/** 顶栏右侧：主题切换按钮（临时版，Task 6 由 ThemeSwitcher 取代）。 */
function ThemeToggle({ theme, setTheme }: { theme: AppTheme; setTheme: (t: AppTheme) => void }) {
  const next: AppTheme = { themeId: 'nous', mode: theme.mode === 'dark' ? 'light' : 'dark' };
  return (
    <button
      className="icon-btn"
      onClick={() => setTheme(next)}
      title="切换明暗主题"
    >
      {theme.mode === 'dark' ? '☀️' : '🌙'}
    </button>
  );
}

/** 顶栏左侧：品牌 + 副标题。 */
function Brand() {
  return (
    <div className="brand">
      <Link to="/" className="brand-link">
        <h1>stok-mapping 网站控制台</h1>
      </Link>
      <p>A股 / 美股 指数与个股走势 · 归一化对照看板</p>
    </div>
  );
}

/** 顶部固定导航栏。 */
function Navbar({ className }: { className?: string }) {
  const nav = useNavigation();
  return (
    <nav className={`navbar${nav.state === 'loading' ? ' loading' : ''}${className ? ' ' + className : ''}`}>
      {NAV.map((n) => (
        <NavLink
          key={n.to}
          to={n.to}
          end={n.to === '/'}
          className={({ isActive, isPending }) =>
            isPending ? 'nav-link pending' : isActive ? 'nav-link active' : 'nav-link'
          }
        >
          {n.label}
        </NavLink>
      ))}
    </nav>
  );
}

/** 全局布局：顶栏导航 + 内容区（<Outlet />）。临时版，Task 6 重写为双层。 */
export function Layout() {
  const [theme, setTheme] = useState<AppTheme>(loadTheme);

  useEffect(() => {
    applyRootTheme(theme);
  }, [theme]);

  useEffect(() => {
    saveTheme(theme);
  }, [theme]);

  return (
    <ThemeContext.Provider value={theme}>
      <div className="page">
        <header className="toolbar">
          <Brand />
          <Navbar />
          <div className="toolbar-right">
            <ThemeToggle theme={theme} setTheme={setTheme} />
          </div>
        </header>

        <main className="content">
          <Outlet />
        </main>
      </div>
    </ThemeContext.Provider>
  );
}

export { Navbar, Brand, ThemeToggle };
