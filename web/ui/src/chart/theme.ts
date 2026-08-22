import type { MaSpan } from '../lib/dashboard';

export type Mode = 'dark' | 'light';
export type ThemeId = 'nous' | 'belafonte';

/** 主题选择：主题注册表 id + 明暗模式。 */
export interface AppTheme {
  themeId: ThemeId;
  mode: Mode;
}

export interface ThemePalette {
  bg: string;
  panel: string;
  border: string;
  text: string;
  dim: string;
  axisLine: string;
  splitLine: string;
  tooltipBg: string;
  tooltipBorder: string;
  up: string;
  down: string;
  /** 美股标的涨/跌色（橙涨/蓝跌）；目标标的使用 A 股通用红涨/绿跌。 */
  soxUp: string;
  soxDown: string;
  ma: Record<MaSpan, string>;
}

/** 主题注册表（每主题每模式一套；与 index.css --ui-* 同步维护，CSS 为事实源）。
 * 完整色值表：docs/WEBSITE_NAVIGATION_STRUCTURE.md §10.1 */
export const THEMES: Record<ThemeId, Record<Mode, ThemePalette>> = {
  nous: {
    dark: {
      bg: '#12378f', panel: '#12378f', border: '#3158ad',
      text: '#ffe6cb', dim: '#b5c7f3',
      axisLine: '#3a63bd', splitLine: '#234a9c',
      tooltipBg: '#183f9a', tooltipBorder: '#3158ad',
      up: '#ef232a', down: '#14b143',
      soxUp: '#e8862e', soxDown: '#3b82f6',
      ma: { 5: '#f6d365', 10: '#ff8fab', 20: '#b388ff', 30: '#6ee7b7', 60: '#4fc3f7' },
    },
    light: {
      bg: '#ffffff', panel: '#ffffff', border: 'rgba(0,83,253,0.22)',
      text: '#17171a', dim: '#666678',
      axisLine: '#0053fd', splitLine: 'rgba(0,83,253,0.24)',
      tooltipBg: '#f2f5ff', tooltipBorder: 'rgba(0,83,253,0.22)',
      up: '#dc2626', down: '#16a34a',
      soxUp: '#e8862e', soxDown: '#3b82f6',
      ma: { 5: '#eab308', 10: '#ec4899', 20: '#8b5cf6', 30: '#10b981', 60: '#0ea5e9' },
    },
  },
  belafonte: {
    dark: {
      bg: '#281822', panel: '#281822', border: '#3d2d36',
      text: '#b88f55', dim: '#96754e',
      axisLine: '#3d2d36', splitLine: '#2a1e26',
      tooltipBg: '#2a1e26', tooltipBorder: '#3d2d36',
      up: '#d94a48', down: '#14b143',
      soxUp: '#e8862e', soxDown: '#3b82f6',
      ma: { 5: '#f6d365', 10: '#ff8fab', 20: '#b388ff', 30: '#6ee7b7', 60: '#4fc3f7' },
    },
    light: {
      bg: '#ded8c8', panel: '#ded8c8', border: '#b8b0a4',
      text: '#45373c', dim: '#5e5252',
      axisLine: '#8a827b', splitLine: '#e8e4dc',
      tooltipBg: '#f3ead6', tooltipBorder: '#b8b0a4',
      up: '#be100e', down: '#16a34a',
      soxUp: '#e8862e', soxDown: '#3b82f6',
      ma: { 5: '#d08b30', 10: '#8b5cf6', 20: '#426a79', 30: '#16a34a', 60: '#0ea5e9' },
    },
  },
};

export function pal(t: AppTheme): ThemePalette {
  return THEMES[t.themeId][t.mode];
}

/** ECharts 数字/文本字体（与 index.css --font-mono 一致，Hermes 风格）。 */
export const CHART_FONT = 'Menlo, Monaco, "SF Mono", "Courier Prime", monospace';
