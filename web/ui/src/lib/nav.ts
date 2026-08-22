/** 网站导航单一数据源：6 域（首层）→ 每域子页（第二层顶栏 tab）。
 * 设计依据：docs/WEBSITE_NAVIGATION_STRUCTURE.md §3/§4。
 */
export type DomainId = 'market' | 'research' | 'intel' | 'accounts' | 'config' | 'ops';

export interface NavPage {
  to: string;
  label: string;
  /** 渲染为下拉菜单（子项动态，如模拟账户列表）；true 时忽略 to 的导航语义。 */
  menu?: boolean;
}

export interface Domain {
  id: DomainId;
  label: string;
  icon: string;
  defaultPath: string;
  pages: NavPage[];
}

export const DOMAINS: Domain[] = [
  {
    id: 'market', label: '行情', icon: '📈', defaultPath: '/market/cn',
    pages: [
      { to: '/market/cn', label: 'A股单标的' },
      { to: '/market/dash', label: 'A股对照' },
      { to: '/market/us', label: '美股单标的' },
    ],
  },
  {
    id: 'research', label: '研究', icon: '🔬', defaultPath: '/research/strategies',
    pages: [
      { to: '/research/strategies', label: '策略' },
      { to: '/research/sox-vs-512480', label: 'SOX对照' },
      { to: '/research/vix-vs-512480', label: 'VIX对照' },
      { to: '/research/compare', label: '任意对比' },
      { to: '/research/wiki', label: '全景图' },
    ],
  },
  {
    id: 'intel', label: '情报', icon: '📰', defaultPath: '/intel/candidates',
    pages: [
      { to: '/intel/candidates', label: '候选' },
      { to: '/intel/corpus', label: '语料' },
      { to: '/intel/signals', label: '信号' },
    ],
  },
  {
    id: 'accounts', label: '账户', icon: '💰', defaultPath: '/accounts',
    pages: [
      { to: '/accounts', label: '总览' },
      { to: '/accounts/brief', label: '每日简报' },
      { to: '/accounts', label: '模拟账户', menu: true },
    ],
  },
  {
    id: 'config', label: '配置', icon: '⚙️', defaultPath: '/config/strategies',
    pages: [
      { to: '/config/strategies', label: '策略参数' },
      { to: '/config/accounts', label: '账户设置' },
      { to: '/config/markets', label: '行情池' },
      { to: '/config/system', label: '系统' },
    ],
  },
  {
    id: 'ops', label: '观测', icon: '🛰️', defaultPath: '/ops/jobs',
    pages: [
      { to: '/ops/jobs', label: '任务' },
      { to: '/ops/scheduler', label: '调度' },
      { to: '/ops/data-health', label: '数据健康' },
    ],
  },
];

/** 按 pathname 推导当前域（/market/us → market 域）。 */
export function domainForPath(pathname: string): Domain | undefined {
  const seg = pathname.split('/')[1];
  return DOMAINS.find((d) => d.id === seg);
}
