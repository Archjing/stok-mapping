import { createBrowserRouter, createHashRouter, Navigate, RouterProvider } from 'react-router-dom';
import { Layout } from './components/Layout';
import { PlaceholderPage } from './components/PlaceholderPage';
import { CnSinglePage } from './pages/CnSinglePage';
import { CnDashPage } from './pages/CnDashPage';
import { UsSinglePage } from './pages/UsSinglePage';
import { AccountsPage } from './pages/AccountsPage';
import { AccountPage } from './pages/AccountPage';
import { WatchlistPage } from './pages/WatchlistPage';
import { BillPage } from './pages/BillPage';
import { LedgerPage } from './pages/LedgerPage';
import { BriefPage } from './pages/BriefPage';
import { ResearchComparisonPage } from './pages/ResearchComparisonPage';
import { AccountChartsPage } from './pages/AccountChartsPage';
import { ComparePage } from './pages/ComparePage';
import { WikiPage } from './pages/WikiPage';

/** 路由：Layout 承载侧栏(首层)+顶栏(第二层)，各域页作为 Outlet。
 * 设计依据：docs/WEBSITE_NAVIGATION_STRUCTURE.md §4/§8。
 * 路由模式：默认 history（本地 8010）；快照构建用 VITE_ROUTER_MODE=hash
 * （静态托管下深链刷新不 404，见 scripts/sync_dashboard_snapshot.sh）。 */
const routes = [
  {
    path: '/',
    element: <Layout />,
    children: [
      // 首页去除：进站直接落到行情默认页
      { index: true, element: <Navigate to="/market/cn" replace /> },

      // 行情（已实现）
      { path: 'market/cn', element: <CnSinglePage /> },
      { path: 'market/dash', element: <CnDashPage /> },
      { path: 'market/us', element: <UsSinglePage /> },

      // 研究（占位；对照图已补全，策略/回测后续）
      { path: 'research/strategies', element: <PlaceholderPage title="策略列表" desc="已注册策略卡片（32 个）——M2 实施" /> },
      { path: 'research/sox-vs-512480', element: <ResearchComparisonPage slug="sox-vs-512480" title="^SOX 与半导体 ETF（512480）对照图" /> },
      { path: 'research/vix-vs-512480', element: <ResearchComparisonPage slug="vix-vs-512480" title="^VIX 与半导体 ETF（512480）对照图" /> },
      { path: 'research/compare', element: <ComparePage /> },
      { path: 'research/wiki', element: <WikiPage /> },
      { path: 'research/runs/new', element: <PlaceholderPage title="回测运行器" desc="preset / strategy-set / run 配置选择——M2 实施" /> },
      { path: 'research/admission', element: <PlaceholderPage title="准入" desc="admission 窗口矩阵 / 约束审查——M2 实施" /> },
      { path: 'research/runs', element: <PlaceholderPage title="运行对比" desc="run 索引横向对比——M2 实施" /> },

      // 情报（占位；/intel/signals 为信号构建预留）
      { path: 'intel/candidates', element: <PlaceholderPage title="情报候选" desc="采集 / 审查 / 入库——M1 只读实施" /> },
      { path: 'intel/corpus', element: <PlaceholderPage title="语料检索" desc="ai_corpus 新闻 / 公告查询——M1 只读实施" /> },
      { path: 'intel/signals', element: <PlaceholderPage title="信号构建" desc="情报 → 策略信号（预留设计）——M2 实施" /> },

      // 账户（占位；动态刷新 P2）
      { path: 'accounts', element: <AccountsPage /> },
      { path: 'accounts/brief', element: <BriefPage /> },
      { path: 'accounts/:accountId', element: <AccountPage /> },
      { path: 'accounts/:accountId/watchlist', element: <WatchlistPage /> },
      { path: 'accounts/:accountId/bill', element: <BillPage /> },
      { path: 'accounts/:accountId/ledger', element: <LedgerPage /> },
      { path: 'accounts/:accountId/charts', element: <AccountChartsPage /> },

      // 配置（占位；策略参数编辑器 M1.5 只读版先行）
      { path: 'config/strategies', element: <PlaceholderPage title="策略参数" desc="run 配置编辑器——M1.5 只读版先行" /> },
      { path: 'config/accounts', element: <PlaceholderPage title="账户设置" desc="config.yaml accounts 子集——M2 实施" /> },
      { path: 'config/markets', element: <PlaceholderPage title="行情池" desc="dashboard_indices 标的组——M1.5 实施" /> },
      { path: 'config/system', element: <PlaceholderPage title="系统" desc="数据源 / 环境 / 路径——M2 实施" /> },

      // 观测（占位）
      { path: 'ops/jobs', element: <PlaceholderPage title="任务队列" desc="web_jobs 列表 / 进度——M2 实施" /> },
      { path: 'ops/scheduler', element: <PlaceholderPage title="调度状态" desc="maintain status——M2 实施" /> },
      { path: 'ops/data-health', element: <PlaceholderPage title="数据健康" desc="db-health / 回填审计——M2 实施" /> },

      // 未知 URL 兜底：回行情默认页
      { path: '*', element: <Navigate to="/market/cn" replace /> },
    ],
  },
];

const router =
  import.meta.env.VITE_ROUTER_MODE === 'hash'
    ? createHashRouter(routes)
    : createBrowserRouter(routes);

export function App() {
  return <RouterProvider router={router} />;
}
