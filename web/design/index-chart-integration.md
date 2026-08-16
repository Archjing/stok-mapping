# index-chart 纳入 WEBSITE_DESIGN_PLAN 架构 — 设计笔记（草稿）

> 状态：待评审。本笔记在 `website-design-dev-20260816` worktree 内，承接 `docs/WEBSITE_DESIGN_PLAN.md`。
> 目标：把现有独立的 `web/index-chart`（Vite+TS+ECharts 单文件静态应用）并入计划书的 FastAPI + React 控制台，作为控制台的一个页面继续演进，并在同一流程内解锁「个股动态加载」需求。

## 0. 现状（已核实）

- `web/index-chart` 是**独立静态应用**：Vite+TypeScript+ECharts（原生 TS，无框架），数据内联（`extract.ts`→`src/generated/data.ts`），构建成单文件 `dist/index.html`，由自己的 `deploy.sh` rsync 到 `/var/www/share/index-chart/`。
- 功能：单指数蜡烛图（缩放粒度日/周/月/年K、MA 开关）+ 对照看板（多标的归一化：窗口/首日/波动率/z-score）。
- 关键纯逻辑已是**框架无关**：`src/aggregate.ts`（K线粒度聚合）、`src/dashboard.ts`（仿射归一化引擎、sma、取色）无 DOM/无 ECharts 依赖，可原样迁入 React。
- 数据源：指数=`market_index_bars`，个股=`market_daily_bars(qfq)`；当前靠构建期抽取，运行时零请求。
- 已有静态站点管线（`quant/reporting/quant_static_site.py` + `site build/sync/publish` + 调度器 `intraday_bill_publish`/`account_bill_confirm` 触发）是**另一套**：从 `quant.*` 生成账户/观察池/对照图 HTML，rsync 到 `/var/www/share/quant/`。

## 1. 定位（对齐计划书 D7）

- **主界面**：本机动态控制台（FastAPI + React），index-chart 成为其中一个路由（建议 `/market/chart`）。
- **静态站点降级**：计划书 D7 明确「静态站点长期降级为离线备份/发布快照；`site publish` rsync 保留给外部只读分享」。index-chart 的「单文件/静态快照」形态保留为同一场景的只读产物，不再作为主开发线。

## 2. 目录（落在 worktree 的 `web/` 下，对齐计划书 §6.1）

```
web/
├─ app/                        # FastAPI（薄 API，import quant.* + 直查 sqlite）
│  ├─ main.py                  # app 工厂；生产托管 web/ui/dist；/api 路由
│  ├─ api/market.py            # /api/market/*（见 §4）
│  ├─ schemas.py               # Pydantic 模型
│  └─ auth.py                  # D6：本机单用户 token（写端点），读端点可同 token
└─ ui/                         # Vite + React 18 + TS + Tailwind + ECharts
   ├─ src/pages/MarketChart/   # index-chart 迁移页
   ├─ src/components/          # <KLineChart> / <ComparisonDashboard> / <MaToggles>…
   ├─ src/lib/                 # 纯逻辑：aggregate.ts、dashboard.ts（原样迁入）
   ├─ src/api/                 # TanStack Query hooks
   └─ src/theme/               # Belafonte design tokens
```

- `data/web_jobs.sqlite`（计划书 D5/D2）按 M2 再加；M1 只读不需要。
- 现有 `web/index-chart` 的独立 `extract.ts`/`deploy.sh` 保留，但降级为「静态快照导出」工具（§5）。

## 3. index-chart 的拆分与迁移

| 现有模块 | 迁移方式 |
| --- | --- |
| `src/aggregate.ts`（粒度聚合）、`src/dashboard.ts`（归一化/取色/sma） | **原样迁入** `web/ui/src/lib/`，零改动（纯函数） |
| `src/main.ts` 里的 ECharts option 组装 + dataZoom 交互 | 封装为 React 组件 + `useECharts` hook，交互逻辑保留 |
| 主题（明/暗） | 并入控制台 `theme/`（Belafonte）；图表内部配色沿用现有 scheme 或统一 token |
| `INDEX_DATA` 内联数据 | 替换为 TanStack Query 拉 `/api/market/*`；静态快照仍由 `extract.ts` 生成 |
| 单文件构建/`deploy.sh` | 保留为「只读快照」发布（§5），主开发走 FastAPI 托管 |

## 4. 只读数据 API（M1，同时解锁「个股动态加载」）

```
GET /api/market/instruments?kind=index|stock        # 元数据(symbol,name,kind,list_date)
GET /api/market/bars/{symbol}?adjust=qfq&start=&end=  # OHLC 日线
GET /api/market/bars/{symbol}?recent=1y               # 近一年（首屏秒开）
GET /api/market/search?q=600519|茅台                  # 代码/名称搜索（market_stocks）
```

- 实现：指数→`market_index_bars`（合并 D/daily 频率），个股→`market_daily_bars(qfq)`；复用 `quant.data_access.local_history` 的读取函数。
- **「近一年先行 + 缓存 + 后台补全」**：前端分两次请求（`recent=1y` 先渲染 → 再拉 `start=全量` 补全），TanStack Query 缓存；符合用户此前设计。
- 纪律（D1）：API 层只做参数翻译 + 读 sqlite，不放业务逻辑；图表计算（聚合/归一化）仍在前端 `ui/src/lib`。

## 5. 远端部署取舍（关键约束）

远端 `share.spidermanread.men` 是**静态托管**（nginx 服务 `/var/www/share`，rsync HTML），当前**不能跑 FastAPI**。因此：

| 模式 | 数据 | 能力 |
| --- | --- | --- |
| **本机开发/生产**（127.0.0.1，uvicorn） | 实时查 sqlite | 全功能：个股搜索、动态加载 |
| **远端只读快照**（rsync） | 预生成 JSON 分片（指数+标的池+可选全市场个股） | 静态只读：图表可看，个股搜索读分片（受限） |
| （可选）远端部署 FastAPI | 实时查远端 sqlite | 完整动态，但需 systemd 常驻 + D6 token + 权限收敛 |

短期建议：**本机动态（主）+ 远端静态快照（分享）**；个股动态加载先在本机完整实现，远端是否要完整动态由后续运维投入决定。

## 6. 分阶段（在 worktree 内）

> 状态更新于 2026-08-16。已确认决策：主题沿用 index-chart 现有明暗配色；认证 D6 只要求写端点；远端=本机动态 + 静态快照。

- **P0 骨架 ✅ 完成**（commit `36bf51d4`）：FastAPI 薄 API（`/api/market/{instruments,bars,search}` 只读直查 sqlite）+ Vite+React+TS 骨架（dev 代理 /api→8010）。注：8000 被本机模型服务占用，FastAPI 开发端口用 **8010**。
- **P1a 单指数 K线图迁移 ✅ 完成**（commits `767a4245`/`80a45f5b`/`007d023e`/`5a40a314`）：纯逻辑 `aggregate/dashboard/data-types` 原样迁入 `web/ui/src/lib`；`<KLineChart>`（蜡烛 + MA 开关 + 缩放粒度日/周/月/年K + 区间 + 读数条）接 `/api/market/bars/{symbol}`；指数切换固定 4 个核心指数；视觉照搬旧 `web/index-chart`。
- **P1b 对照看板 + 个股搜索动态加载 ⏳ 待做**：
  1. `<ComparisonDashboard>` 组件（多标的 checkbox + 归一化窗口/首日/波动率/z-score + 对比方式蜡烛/收盘/均线），复用 `dashboard.ts` 归一化引擎与 `/api/market/instruments|bars`；
  2. 个股搜索：`/api/market/search` + 输入框 → 「近一年先行（`?recent=1y`）渲染 + 后台拉全量补全」+ 前端缓存；
  3. 视图切换（单指数 / 对照看板）挂回顶栏。
- **P2 M1 其余只读页**：账户/观察池/对照图（复用 `quant.reporting`）。
- **P3 M2 写操作**：任务队列（`web_jobs` + 进程池）+ 写端点 + `run_index`。

## 7. 决策点 / 风险

1. 图表库：仍 ECharts（计划书首选）；K线场景后续可评估 Lightweight Charts。
2. 主题：控制台统一 Belafonte；index-chart 现有明暗配色是否并入需你拍板（你此前说视觉暂缓）。
3. 认证：只读端点本机 127.0.0.1 是否也要 token（D6 默认写端点要求；只读可放宽）。
4. 数据口径：个股一律 qfq（前复权）；指数合并 D/daily 频率——与 index-chart 现状一致，避免口径漂移。
5. 迁移不破坏现有静态分享：`web/index-chart` 的 `deploy.sh` 在 P0/P1 期间保持可发布，直到新 UI 能产出等价只读快照。
