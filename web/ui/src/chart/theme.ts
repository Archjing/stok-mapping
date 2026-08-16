import type { MaSpan } from '../lib/dashboard';

export type Theme = 'dark' | 'light';

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
  ma: Record<MaSpan, string>;
}

/** index-chart 现有明暗配色（沿用，暂不并入 Belafonte） */
export const THEMES: Record<Theme, ThemePalette> = {
  dark: {
    bg: '#151d2b',
    panel: '#151d2b',
    border: '#2b3950',
    text: '#eef3fa',
    dim: '#a2b3c8',
    axisLine: '#3a4a66',
    splitLine: '#202b3d',
    tooltipBg: '#1a2434',
    tooltipBorder: '#33415c',
    up: '#ef232a',
    down: '#14b143',
    ma: { 5: '#f6d365', 10: '#ff8fab', 20: '#b388ff', 30: '#6ee7b7', 60: '#4fc3f7' },
  },
  light: {
    bg: '#ffffff',
    panel: '#ffffff',
    border: '#c9d3df',
    text: '#101827',
    dim: '#56697e',
    axisLine: '#8fa1b8',
    splitLine: '#e6ebf2',
    tooltipBg: '#ffffff',
    tooltipBorder: '#c9d3df',
    up: '#dc2626',
    down: '#16a34a',
    ma: { 5: '#eab308', 10: '#ec4899', 20: '#8b5cf6', 30: '#10b981', 60: '#0ea5e9' },
  },
};

export function pal(theme: Theme): ThemePalette {
  return THEMES[theme];
}
