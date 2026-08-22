import { useEffect, useRef, useState } from 'react';
import type { AppTheme, Mode, ThemeId } from '../chart/theme';

const OPTIONS: Array<{ themeId: ThemeId; mode: Mode; label: string }> = [
  { themeId: 'nous', mode: 'dark', label: 'Nous Dark' },
  { themeId: 'nous', mode: 'light', label: 'Nous Light' },
  { themeId: 'belafonte', mode: 'dark', label: 'Belafonte Night' },
  { themeId: 'belafonte', mode: 'light', label: 'Belafonte Day' },
];

/** 顶栏主题选择器：按钮显示当前主题名，点击弹出 4 项菜单。 */
export function ThemeSwitcher({
  theme,
  onChange,
}: {
  theme: AppTheme;
  onChange: (t: AppTheme) => void;
}) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const current = OPTIONS.find((o) => o.themeId === theme.themeId && o.mode === theme.mode) ?? OPTIONS[0];

  // 点击外部关闭菜单
  useEffect(() => {
    if (!open) return;
    const onDocClick = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('click', onDocClick);
    return () => document.removeEventListener('click', onDocClick);
  }, [open]);

  return (
    <div className="theme-switcher" ref={rootRef}>
      <button className="icon-btn theme-switcher-btn" onClick={() => setOpen((v) => !v)} title="切换主题">
        🎨 {current.label}
      </button>
      {open && (
        <div className="theme-menu">
          {OPTIONS.map((o) => (
            <button
              key={`${o.themeId}-${o.mode}`}
              className={`theme-menu-item${o.themeId === theme.themeId && o.mode === theme.mode ? ' active' : ''}`}
              onClick={() => {
                onChange({ themeId: o.themeId, mode: o.mode });
                setOpen(false);
              }}
            >
              {o.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
