import { createContext, useContext } from 'react';
import type { Theme } from '../chart/theme';

/**
 * 全局明暗主题上下文。
 * Layout 持有 theme state 并通过 <ThemeContext.Provider> 下发给所有子页，
 * 子页用 useTheme() 取当前主题（避免硬编码 'dark' 导致图表明暗联动失效）。
 */
export const ThemeContext = createContext<Theme>('dark');

export function useTheme(): Theme {
  return useContext(ThemeContext);
}
