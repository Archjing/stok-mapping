import { Link, NavLink, Outlet, useLocation, useNavigation } from 'react-router-dom';
import { useEffect, useState } from 'react';
import type { AppTheme } from '../chart/theme';
import { ThemeContext, applyRootTheme, loadTheme, saveTheme } from './ThemeContext';
import { ThemeSwitcher } from './ThemeSwitcher';
import { DOMAINS, domainForPath, type Domain } from '../lib/nav';

const SIDEBAR_KEY = 'website-sidebar-collapsed';

function initialCollapsed(): boolean {
  try {
    return localStorage.getItem(SIDEBAR_KEY) === '1';
  } catch {
    return false;
  }
}

/** 侧栏（第一层）：领域切换；收起为 44px 窄条（箭头按钮位置/形式不变）。 */
function Sidebar({
  collapsed,
  onToggle,
  theme,
  onThemeChange,
}: {
  collapsed: boolean;
  onToggle: () => void;
  theme: AppTheme;
  onThemeChange: (t: AppTheme) => void;
}) {
  const location = useLocation();
  const activeId = domainForPath(location.pathname)?.id;
  return (
    <aside className={`sidebar${collapsed ? ' collapsed' : ''}`}>
      <div className="sidebar-head">
        <Link to="/market/cn" className="sidebar-brand">
          stok-mapping
        </Link>
        <button className="icon-btn sidebar-toggle" onClick={onToggle} title={collapsed ? '展开侧栏' : '收起侧栏'}>
          {collapsed ? '▶' : '◀'}
        </button>
      </div>
      <nav className="sidebar-nav">
        {DOMAINS.map((d) => (
          <NavLink
            key={d.id}
            to={d.defaultPath}
            className={`sidebar-item${activeId === d.id ? ' active' : ''}`}
            title={d.label}
          >
            <span className="sidebar-icon">{d.icon}</span>
            <span className="sidebar-label">{d.label}</span>
          </NavLink>
        ))}
      </nav>
      <div className="sidebar-footer">
        <ThemeSwitcher theme={theme} onChange={onThemeChange} />
      </div>
    </aside>
  );
}

/** 顶栏（第二层）：当前域的子页 tab。 */
function TopNav({ domain }: { domain: Domain }) {
  const nav = useNavigation();
  return (
    <nav className={`topnav${nav.state === 'loading' ? ' loading' : ''}`}>
      {domain.pages.map((p) => (
        <NavLink
          key={p.to}
          to={p.to}
          end={p.to === domain.defaultPath}
          className={({ isActive, isPending }) =>
            isPending ? 'topnav-link pending' : isActive ? 'topnav-link active' : 'topnav-link'
          }
        >
          {p.label}
        </NavLink>
      ))}
    </nav>
  );
}

/** 全局布局：侧栏（首层）+ 顶栏（第二层）+ 内容区（<Outlet />）。 */
export function Layout() {
  const [theme, setTheme] = useState<AppTheme>(loadTheme);
  const [collapsed, setCollapsed] = useState<boolean>(initialCollapsed);
  const location = useLocation();
  const domain = domainForPath(location.pathname) ?? DOMAINS[0];

  useEffect(() => {
    applyRootTheme(theme);
  }, [theme]);

  useEffect(() => {
    saveTheme(theme);
  }, [theme]);

  useEffect(() => {
    try {
      localStorage.setItem(SIDEBAR_KEY, collapsed ? '1' : '0');
    } catch {
      /* 忽略 */
    }
  }, [collapsed]);

  return (
    <ThemeContext.Provider value={theme}>
      <div className={`page${collapsed ? ' sidebar-collapsed' : ''}`}>
        <Sidebar
          collapsed={collapsed}
          onToggle={() => setCollapsed((c) => !c)}
          theme={theme}
          onThemeChange={setTheme}
        />
        <div className="page-main">
          <header className="toolbar">
            <TopNav domain={domain} />
          </header>
          <main className="content">
            <Outlet />
          </main>
        </div>
      </div>
    </ThemeContext.Provider>
  );
}
