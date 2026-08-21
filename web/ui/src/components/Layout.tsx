import { Link, NavLink, Outlet, useNavigation } from 'react-router-dom';
import { useEffect, useState } from 'react';
import type { Theme } from '../chart/theme';
import { ThemeContext } from './ThemeContext';

/** 导航项：label + 目标路由。首页也带同一导航栏。 */
const NAV: Array<{ to: string; label: string }> = [
  { to: '/', label: '首页' },
  { to: '/market/cn', label: 'A股单标的' },
  { to: '/market/dash', label: 'A股对照' },
  { to: '/market/us', label: '美股单标的' },
];

function initialTheme(): Theme {
  try {
    return (localStorage.getItem('index-chart-theme') as Theme) || 'dark';
  } catch {
    return 'dark';
  }
}
function applyRootTheme(t: Theme): void {
  document.documentElement.dataset.theme = t;
}

/** 顶栏右侧：主题切换按钮。 */
function ThemeToggle({ theme, setTheme }: { theme: Theme; setTheme: (t: Theme) => void }) {
  return (
    <button
      className="icon-btn"
      onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
      title="切换明暗主题"
    >
      {theme === 'dark' ? '☀️' : '🌙'}
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

/** 全局布局：顶栏导航 + 内容区（<Outlet />）。 */
export function Layout() {
  const [theme, setTheme] = useState<Theme>(initialTheme);

  useEffect(() => {
    applyRootTheme(theme);
  }, [theme]);

  return (
    <ThemeContext.Provider value={theme}>
      <div className="page" data-theme={theme}>
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
