import { createContext, useContext } from 'react';
import type { AppTheme } from '../chart/theme';

const THEME_KEY = 'website-theme';
const LEGACY_KEY = 'index-chart-theme';

export const DEFAULT_THEME: AppTheme = { themeId: 'nous', mode: 'dark' };

/** 读取持久化主题；兼容旧 key index-chart-theme（dark/light → nous + 对应 mode）。 */
export function loadTheme(): AppTheme {
  try {
    const raw = localStorage.getItem(THEME_KEY);
    if (raw) {
      const t = JSON.parse(raw) as AppTheme;
      if ((t.themeId === 'nous' || t.themeId === 'belafonte') && (t.mode === 'dark' || t.mode === 'light')) {
        return t;
      }
    }
    const legacy = localStorage.getItem(LEGACY_KEY);
    if (legacy === 'dark' || legacy === 'light') {
      return { themeId: 'nous', mode: legacy };
    }
  } catch {
    /* localStorage 不可用时用默认 */
  }
  return DEFAULT_THEME;
}

export function saveTheme(t: AppTheme): void {
  try {
    localStorage.setItem(THEME_KEY, JSON.stringify(t));
  } catch {
    /* 忽略 */
  }
}

/** 应用到 <html>：data-theme + data-mode 双属性（CSS 选择器 [data-theme][data-mode]）。 */
export function applyRootTheme(t: AppTheme): void {
  document.documentElement.dataset.theme = t.themeId;
  document.documentElement.dataset.mode = t.mode;
}

const ThemeContext = createContext<AppTheme>(DEFAULT_THEME);

export function useTheme(): AppTheme {
  return useContext(ThemeContext);
}

export { ThemeContext };
