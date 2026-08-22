# stok-mapping 网站导航结构与配置域设计定稿

> 状态：**定稿**（2026-08-22）
> 关联文档：[WEBSITE_DESIGN_PLAN.md](WEBSITE_DESIGN_PLAN.md)（总体计划，唯一事实源）、[index-chart-integration.md](../web/design/index-chart-integration.md)（P0–P1c 实施笔记）
> 范围：双层导航结构 + 六域首层分类 + 配置域·策略参数编辑器细化设计

---

## 1. 总览

网站采用**双层导航**：侧栏为第一层（领域切换），顶栏为第二层（域内子页 tab，随当前领域变化）。首层按用户心智动作分为 **6 个域**：行情 / 研究 / 情报 / 账户 / 配置 / 观测。

```
┌──────────┬────────────────────────────────────────┐
│ 侧栏(第一层)│ 顶栏(第二层，随域变化)                    │
│ 行情        │  A股单标的 | A股对照 | 美股单标的          │
│ 研究        ├────────────────────────────────────────┤
│ 情报        │                                        │
│ 账户        │             内容区                     │
│ 配置        │                                        │
│ 观测        │                                        │
└──────────┴────────────────────────────────────────┘
```

## 2. 双层导航

### 2.1 侧栏（第一层，领域导航）

- 固定左缘，6 个领域项纵向排列，当前域高亮
- **收起交互**：顶部 ◀ 箭头点击 → 整栏向左滑出（220px → 0，CSS transition），内容区自适应扩宽；收起后**仅留 8px 竖条把手**（hover/点击展开）
- 收起状态存 `localStorage`，刷新保持
- 层级规则：侧栏切领域 → 顶栏 tab 自动切到该域默认页；URL 结构 `/domain/page`，深链直达

### 2.2 顶栏（第二层，域内导航）

- 随当前领域变化的子页 tab（数据源为 `nav.ts`，见 §8）
- 右侧保留：主题切换（现有 ThemeToggle）；未来加数据刷新状态指示（轮询中/已更新）

### 2.3 定稿决策

| # | 决策点 | 定稿 |
|---|---|---|
| 1 | 首页去留 | **移除 HomePage**，`/` → 302 重定向 `/market/cn`，进站即行情 |
| 2 | 侧栏收起形态 | **完全收起**（0 宽度），仅留竖条把手 |
| 3 | 配置写入路径 | **生成 run 配置**（不写 config.yaml 主文件）；直接改主配置仅作 M2 后期可选项 |
| 4 | 情报 | **独立成层**，预留"情报→策略信号"设计（见 §6） |

## 3. 首层分类（六域）

| 首层 | 职责 | 状态 |
|---|---|---|
| **行情** Market | 只读市场浏览（A股/美股指数与个股） | ✅ 已实现 |
| **研究** Research | 策略验证主线：策略 / 回测 / 准入 / 对比 | 🚧 规划 |
| **情报** Intelligence | 情报采集、候选审查、语料查询、信号构建（预留） | 🚧 规划 |
| **账户** Accounts | 模拟账户全生命周期（查看 → 动态刷新） | 🚧 P2 |
| **配置** Config | 参数与设置（策略参数编辑器为核心新功能） | 🆕 设计定稿 |
| **观测** Ops | 任务队列 / 调度状态 / 数据健康 | 🚧 M2 |

分类逻辑：

- 按用户心智动作分域（看行情、做研究、收情报、管账户、调配置、查系统）
- 情报独立成层（决策 4）：情报是研究的**输入链**（候选→语料→信号），且预留信号构建能力，未来可能反向影响策略，独立成层避免研究域膨胀
- 配置独立成层：横切所有域（策略/账户/行情/系统参数），是写操作的主要入口
- 观测独立：运维视角，与交易研究分离
- 首层顺序：行情 / 研究 / 情报 / 账户 / 配置 / 观测（按使用频率与工作流，可调）

## 4. 站点地图

| 首层 | 顶栏 tab | 页面 |
|---|---|---|
| 行情 | A股单标的 / A股对照 / 美股单标的 | `/market/cn` `/market/dash` `/market/us`（✅ 已实现） |
| 研究 | 策略 / 回测 / 准入 / 对比 | `/research/strategies` `/:id` `/runs` `/runs/:id` `/runs/new` |
| 情报 | 候选 / 语料 / 信号 | `/intel/candidates` `/intel/corpus` `/intel/signals`（预留占位） |
| 账户 | 总览 / 盘前观察池 | `/accounts` `/:id`（台账账单）`/accounts/premarket` |
| 配置 | 策略参数 / 账户设置 / 行情池 / 系统 | `/config/strategies` `/config/accounts` `/config/markets` `/config/system` |
| 观测 | 任务 / 调度 / 数据健康 | `/ops/jobs` `/ops/scheduler` `/ops/data-health` |

## 5. 配置域 · 策略参数编辑器（细化定稿）

### 5.1 事实基础（已核实代码）

- 策略参数**不是代码硬编码**：config.yaml 里每个策略一个配置节（`strategy_cfg.<strategy_id>`），是 walk-forward 网格搜索的候选空间
- `select_params()` 在训练窗口上网格搜索，选出最终 `params`（如 `mom_window`、`buy_threshold`）；`apply()` 消费
- 每个策略参数形态不统一（3–12 个参数；类型 = list[number] / number / bool）；**无现成参数声明元数据**（`base.py` 仅抽象方法）
- 全局还有两层：运行级参数（`walk_forward.execution`：commission/slippage/stamp_duty/initial_cash + presets 窗口）与集合级（strategy_sets）

### 5.2 编辑对象：三个分组

```
配置域 /config/strategies
├─ 分组1 策略参数（核心）：32 个已注册策略各自的参数节（搜索空间）
├─ 分组2 运行级参数：commission/slippage/stamp_duty + presets 窗口
└─ 分组3 策略集合：strategy_sets 成员编辑（准入集合，可后置）
```

### 5.3 编辑产物 = run 配置（决策 3）

```
编辑参数 → 保存为命名 run 配置 ──存 SQLite run_configs 表──> 回测运行器可选引用
  不写 config.yaml 主文件              (strategy_id + params 覆盖 + 元数据)
```

- **读路径**：config.yaml（事实源，只读）+ `registry.available_strategies()`（枚举）→ 后端拼出结构化 schema
- **写路径**：run 配置存 `web_jobs.sqlite` 新表 `run_configs`（沿用计划书 D5 web_jobs 规划，同库加表）
- **生效时机**：run 配置是"供下次 run 引用的预设"，不立即生效；M2 给 CLI 加 `--run-config <name>`（在 `walk_forward.py` 的 strategy_cfg 构造处 merge 覆盖）——遵守"先 CLI 后 Web"纪律（计划书 D1 §1.4）

### 5.4 run 配置 schema

```json
{
  "name": "mom_5_20_fast",
  "description": "低换手经典动量：加快调仓",
  "strategy_id": "legacy_momentum_low_turnover_v1",
  "params": { "mom_windows": [5, 10], "buy_quantiles": [0.5], "rebalance_days_values": [5] },
  "created_at": "...",
  "updated_at": "...",
  "used_by": ["run_id..."]
}
```

### 5.5 API 设计

| 方法 | 路径 | 说明 | 阶段 |
|---|---|---|---|
| GET | `/api/config/strategies` | 策略列表（registry 元数据 + enabled 状态） | M1.5 |
| GET | `/api/config/strategies/{id}/params` | 参数 schema：当前值(config) + 类型推断 + 说明 | M1.5 |
| GET | `/api/config/run-configs` | 已保存 run 配置列表 | M1.5 |
| POST | `/api/config/run-configs` | 保存/更新 run 配置（**写端点，D6 token**） | M2 |
| DELETE | `/api/config/run-configs/{id}` | 删除 | M2 |

**参数 schema 推断**（v1 不引入新声明机制）：config 现有值类型即 schema（list→多值输入、bool→开关、number→数字）；参数说明用人工维护小表 `web/app/param_notes.yaml`（先覆盖常用策略），避免给 `base.py` 全量加 schema 声明（违反最小改动）。

### 5.6 前端页面结构（/config/strategies）

```
┌─────────────┬──────────────────────────────────────────┐
│ 策略列表      │ 参数表单（选中策略）                        │
│ [搜索框]     │ 分组：搜索空间 / 执行约束 / 跨市场开关        │
│ ☑ enabled过滤 │  mom_windows  [5, 20]        ⟲重置        │
│ 低换手经典动量 │  buy_quantiles [0.6]         ⟲重置        │
│ 经典动量      │  target_vol    0.18           ⟲重置        │
│ 质量成长价格  │                                    [↕默认diff] │
│ ...(32)     │  ────────────────────────────────────    │
│             │  名称:[mom_5_20_fast] 描述:[...]          │
│             │  [保存为 run 配置]                        │
└─────────────┴──────────────────────────────────────────┘
  [已保存配置抽屉] mom_5_20_fast (3参数覆盖) · mom_q1 (5覆盖) · 删除/复用
```

- 每个参数行：名称 | 说明 | 当前值（可编辑）| 默认值徽标 | 单参数重置
- 保存流程：编辑 → 前端类型校验 → 命名 + 描述 → POST → 出现在"已保存配置"抽屉
- 回测联动：`/research/runs/new` 增加 run 配置选择器（M2）
- 与默认对比：保存前展示 diff（改动参数高亮）

### 5.7 实施阶段与风险

| 阶段 | 内容 |
|---|---|
| M1.5（只读） | 2 个 GET 端点 + 参数浏览页（只读展示，验证 schema 推断质量） |
| M2（写） | `run_configs` 表 + POST/DELETE（token）+ 编辑表单 + 回测运行器集成 + CLI `--run-config` |

风险与边界：

1. **无参数元数据**是最大坑——参数说明靠人工维护表，覆盖不全时显示"无说明"，不臆造
2. **config.yaml 并发写**：本期不写主 config，天然规避 maintain tick 配置读取冲突；M2 后期若开放"直接写 config"必须备份 + diff + 锁
3. **run 配置不校验语义合法性**（如 mom_windows 不在候选范围）→ 前端只做类型校验，语义校验留给 walk-forward 运行时（与 CLI 行为一致）
4. **参数节定位**：config.yaml 里 per-strategy 节缩进层级需在后端读取时精确定位，v1 用防御式读取（找不到节 → 全用代码默认值）

## 6. 情报域 · 信号构建预留

```
情报 /intel
  ├─ /intel/candidates   情报候选：采集列表、审查、入库     (intelligence collect/review/import)
  ├─ /intel/corpus       语料检索：ai_corpus 新闻/公告查询
  ├─ /intel/news         新闻观察：最新情报流（只读）
  └─ /intel/signals      信号构建（预留）：情报 → 策略信号
```

信号构建链路（情报→研究的关键边界）：

```
情报语料(已入库) ──信号提取器(规则/LLM)──> 信号序列 ──落库──> 研究域消费
  新闻/公告          方向+强度+标的+时间戳        signal 表        候选因子/策略输入
```

- 信号层是情报与研究的**边界**：研究域只消费结构化信号，不直接依赖原始语料，避免研究逻辑耦合采集细节
- `/intel/signals` 页面形态：信号列表（标的/时间/方向/强度）+ 信号源配置（哪些情报源→什么信号）+ 信号↔策略关联视图
- 实施节奏：M1 先做情报只读（候选/语料/news），信号提取逻辑 M2 落地；**路由与导航现在就预留 `/intel/signals` 占位**

## 7. 账户域 · 动态刷新

- 只读不改：读端点保持 `GET /api/accounts`，前端加"自动刷新"开关（30s/60s 轮询），盘后 15:05 起数据更新后页面自动更新；显示上次更新时间戳
- M3 升级为 SSE 推送（计划书 D2 已预留 `/api/jobs/{id}/events` 模式）
- 盘前观察池数据复用 `quant.reporting.premarket_watchlist` 输出结构

## 8. 路由与代码影响

```tsx
// 路由结构（改造后）
createBrowserRouter([
  { path: '/', element: <Layout />, children: [
    { index: true, element: <Navigate to="/market/cn" replace /> },
    { path: 'market/*', ... },     // 现有 3 页，零改动
    { path: 'research/*', ... },
    { path: 'intel/*', ... },
    { path: 'accounts/*', ... },
    { path: 'config/*', ... },
    { path: 'ops/*', ... },
  ]},
])
```

- **Layout.tsx 重构**：顶栏导航拆为 侧栏（第一层）+ 顶栏（第二层，由当前域推导）；导航配置抽成单一数据源 `web/ui/src/lib/nav.ts`（domain → pages + 默认页），新增域只改数据
- 现有 `/market/*` 三页和组件**零改动**，只换外壳
- HomePage 移除（决策 1）
- 新页面先建壳（占位内容），后端按 P2/M2 节奏补端点
- 后端拆分：`web/app/main.py` 按计划书 §6.1 拆 `api/` 模块（config.py 先行，其余随功能推进）

## 9. 实施顺序（建议）

1. **导航重构**（先做，独立可验证）：Layout 双层化 + nav.ts + 路由改造 + HomePage 移除 → 现有行情页在新外壳下跑通
2. **配置域 M1.5**：`/api/config/strategies` + `/params` 只读端点 + 参数浏览页（验证 schema 推断）
3. **账户域 P2**：`quant.reporting` 读取端点 + 账户总览/盘前页 + 动态刷新开关
4. **情报域 M1 只读**：候选/语料/news 页 + 信号占位
5. **M2 写操作**：web_jobs + run_configs 表 + 写端点（token）+ 回测运行器 + CLI `--run-config`

---

## 10. UI 设计规范（效仿 Hermes 桌面端，2026-08-22 增补）

> 决策：前端界面效仿 Hermes 桌面端 App（`~/.hermes/hermes-agent/apps/desktop`）的视觉与设计体系；**主题基底 = nous**（品牌蓝 + 奶油，Hermes 默认身份）。设计原则采纳 Hermes DESIGN.md 的 **Flat, not boxed** 与 **hairline** 体系。

### 10.1 Token 分层

**层 1：语义 token**（组件只消费这一层，主题无关；参照 Hermes `--ui-*` 体系）

| 语义 token | 用途 |
|---|---|
| `--ui-bg-app` | 页面底 |
| `--ui-bg-panel` | 面板/内容区底 |
| `--ui-bg-subtle` | 次级填充（hover、选中底、chip） |
| `--ui-bg-quaternary` | 软控制填充（次级按钮） |
| `--ui-text-primary / secondary / tertiary` | 文字三级层级 |
| `--ui-stroke-primary / secondary / tertiary` | 发丝线三级（tertiary = 默认面板分隔线） |
| `--ui-accent` / `--ui-accent-fg` | 品牌强调 / 其上的文字 |
| `--ui-accent-secondary` | 强调底色（选中/hover 底） |
| `--ui-warm` | 暖强调（警示、焦点行） |
| `--ui-danger` | 危险操作 |
| `--ui-shadow-nous` + `--ui-stroke-nous` | 浮动层（菜单/抽屉/tooltip）专用 |
| `--ui-radius-scalar` | 圆角统一缩放 |
| `--ui-up` / `--ui-down` | 涨红跌绿（项目口径，主题无关） |
| `--ui-ma-5/10/20/30/60` | 均线色板（随主题适配） |

**层 2：主题注册表**（效仿 Hermes `BUILTIN_THEMES` 结构；每主题含明暗两套；2026-08-22 决策：多套配色可选，至少含 **nous** 与 **Belafonte**）

```ts
interface ThemePreset {
  id: 'nous' | 'belafonte';   // 后续可加 midnight/slate/ember…
  label: string;
  colors: Record<Mode, UiTokens>;  // Mode = 'dark' | 'light'
}
```

**nous**（Hermes 默认身份；来源 `~/.hermes/hermes-agent/apps/desktop/src/themes/presets.ts` nousTheme，2026-08-22 提取，2026-08-22 严格复刻补齐）

Light（冷白 + Nous 蓝）：

| 语义 token | 值 | 来源 |
|---|---|---|
| `--ui-bg-app` | `#F8FAFF` | background |
| `--ui-bg-panel` | `#FFFFFF` | card |
| `--ui-bg-subtle` | `#F2F5FF` | muted（nousTint 5%） |
| `--ui-bg-quaternary` | `#EFF4FF` | secondary（nousTint 7%） |
| `--ui-text-primary` | `#17171A` | foreground |
| `--ui-text-secondary` | `#666678` | mutedForeground |
| `--ui-text-tertiary` | `#9AA0B4`* | 派生 |
| `--ui-stroke-primary` | rgba(0,83,253,0.30) | input |
| `--ui-stroke-secondary` | rgba(0,83,253,0.24) | userBubbleBorder |
| `--ui-stroke-tertiary` | rgba(0,83,253,0.22) | border |
| `--ui-accent` | `#0053FD` | primary / ring |
| `--ui-accent-fg` | `#FCFCFC` | primaryForeground |
| `--ui-accent-secondary` | `#E6EEFF` | accent（nousTint 10%） |
| `--ui-warm` | `#cf806d` | theme-warm（Hermes 原值，明暗统一） |
| `--ui-danger` | `#C72E4D` | destructive |
| `--ui-up` / `--ui-down` | `#dc2626` / `#16a34a` | 行情口径（沿用现有 light） |
| `--ui-bg-sidebar` | `#F3F7FF` | sidebarBackground |
| `--ui-bg-popover` | `#FFFFFF` | popover |
| `--ui-input-bg` | rgba(0,83,253,0.30) | input |

Dark：

| 语义 token | 值 | 来源 |
|---|---|---|
| `--ui-bg-app` | `#0D2F86` | darkColors.background |
| `--ui-bg-panel` | `#12378F` | card |
| `--ui-bg-subtle` | `#183F9A` | muted |
| `--ui-bg-quaternary` | `#1B45A4` | secondary |
| `--ui-text-primary` | `#FFE6CB` | foreground（psyche 奶油） |
| `--ui-text-secondary` | `#B5C7F3` | mutedForeground |
| `--ui-text-tertiary` | `#8F9FD8`* | 派生 |
| `--ui-stroke-primary` | `#3A63BD` | userBubbleBorder |
| `--ui-stroke-secondary` | `#234A9C` | sidebarBorder |
| `--ui-stroke-tertiary` | `#3158AD` | border |
| `--ui-accent` | `#FFE6CB` | primary（dark 下主按钮奶油底深蓝字） |
| `--ui-accent-fg` | `#0D2F86` | primaryForeground |
| `--ui-accent-secondary` | `#1540B1` | accent（PSYCHE_BLUE） |
| `--ui-warm` | `#cf806d` | theme-warm（Hermes 原值，明暗统一） |
| `--ui-danger` | `#C0473A` | destructive |
| `--ui-up` / `--ui-down` | `#ef232a` / `#14b143` | 行情口径（沿用现有 dark） |
| `--ui-bg-sidebar` | `#09286F` | sidebarBackground |
| `--ui-bg-popover` | `#123A96` | popover |
| `--ui-input-bg` | `#0B2566` | input |

（`*` = 派生值，需在主题底色上人工目检微调）

**Belafonte**（原始主题，静态站点在用；来源 `quant/reporting/static/style.css`）

Day（light，暖羊皮纸）：

| 语义 token | 值 | 来源 |
|---|---|---|
| `--ui-bg-app` | `#fffaed` | bg |
| `--ui-bg-panel` | `#ded8c8` | bg-card |
| `--ui-bg-subtle` | `#e8e4dc` | hover-row |
| `--ui-bg-quaternary` | `#ccc5b8` | tag-bg |
| `--ui-text-primary` | `#45373c` | text |
| `--ui-text-secondary` | `#5e5252` | text-dim |
| `--ui-text-tertiary` | `#8a827b` | text-muted |
| `--ui-stroke-secondary` | `#b8b0a4` 60%* | 派生 |
| `--ui-stroke-tertiary` | `#b8b0a4` | border |
| `--ui-accent` | `#426a79` | accent |
| `--ui-accent-fg` | `#2d4d59` | accent-text |
| `--ui-accent-secondary` | `#cbd5d9` | accent-bg |
| `--ui-warm` | `#d08b30` | amber / focus-strong |
| `--ui-danger` | `#be100e` | red-text |
| `--ui-up` / `--ui-down` | `#be100e` / `#16a34a` | 涨红（red-text）/ 跌绿（沿用） |

Night（dark，深酒红）：

| 语义 token | 值 | 来源 |
|---|---|---|
| `--ui-bg-app` | `#20111b` | bg |
| `--ui-bg-panel` | `#281822` | bg-card |
| `--ui-bg-subtle` | `#2a1e26` | hover-row |
| `--ui-bg-quaternary` | `#3d2d36` | tag-bg / border |
| `--ui-text-primary` | `#b88f55` | text |
| `--ui-text-secondary` | `#96754e` | text-dim |
| `--ui-text-tertiary` | `#6f5a43` | text-muted |
| `--ui-stroke-secondary` | `#3d2d36` 60%* | 派生 |
| `--ui-stroke-tertiary` | `#3d2d36` | border |
| `--ui-accent` | `#5a8a9a` | accent |
| `--ui-accent-fg` | `#7fb4c4` | accent-text |
| `--ui-accent-secondary` | `#233840` | accent-bg |
| `--ui-warm` | `#eaa549` | amber |
| `--ui-danger` | `#d94a48` | red-text |
| `--ui-up` / `--ui-down` | `#d94a48` / `#14b143` | 涨红（red-text）/ 跌绿（沿用） |

（`*` = 派生值，需目检微调；MA 色板 Belafonte 沿用现有 dark/light 值，目检）

### 10.2 主题状态与切换

- 状态模型：`{ themeId: 'nous' | 'belafonte', mode: 'dark' | 'light' }`，HTML 上以 `data-theme="nous"` + `data-mode="dark"` 两个属性表达（CSS 选择器 `[data-theme='nous'][data-mode='dark']`）
- 持久化：`localStorage` key `website-theme`（JSON）；**兼容旧 key** `index-chart-theme`（`dark`/`light` → nous + 对应 mode）
- 切换 UI：顶栏主题按钮（显示当前主题名）→ 弹出菜单 4 项：**Nous Dark / Nous Light / Belafonte Night / Belafonte Day**；菜单用浮动层规范（`--ui-shadow-nous` + `--ui-stroke-nous`，背景 `--ui-bg-popover`）
- 默认：nous + dark

### 10.2b 字体（Hermes 桌面风格）

- `--font-sans`: `'Segoe WPC', 'Segoe UI', -apple-system, BlinkMacSystemFont, 'SF Pro Text', 'SF Pro Display', system-ui, 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif`（Hermes SYSTEM_SANS + 中文 fallback）
- `--font-mono`: `Menlo, Monaco, 'SF Mono', 'Courier Prime', monospace`（Hermes SYSTEM_MONO）
- 应用：body 用 `--font-sans`；数字读数（`.readout`）与 ECharts 图表文本用 `--font-mono`（JS 侧常量 `CHART_FONT`，与 CSS 同步）

### 10.3 现有变量迁移映射

```
--bg          → --ui-bg-app
--panel       → --ui-bg-panel
--panel2      → --ui-bg-subtle
--border      → --ui-stroke-tertiary
--text        → --ui-text-primary
--dim         → --ui-text-secondary
--accent      → --ui-accent
--accent-text → --ui-accent-fg
--chip-bg     → --ui-bg-subtle
--warn        → --ui-warm
--shadow      → --ui-shadow-nous（仅浮动层用）
```

迁移方式：index.css 保留旧变量名做别名（`--panel: var(--ui-bg-panel)`），组件先零改动跑通，再逐步切语义名。

### 10.4 图表适配（chart/theme.ts）

- 结构：`THEMES: Record<ThemeId, Record<Mode, ThemePalette>>`（每主题每模式一套；与 CSS 同步维护，CSS 为事实源）
- bg/panel/border/text/dim → 对应主题语义值
- axisLine / splitLine → stroke 层派生（`color-mix(currentColor 15% / 8%)`）
- tooltipBg / tooltipBorder → `--ui-bg-panel` + `--ui-stroke-tertiary`
- up / down → 每主题各自的 `--ui-up` / `--ui-down`（涨红跌绿口径不变，色值随主题）
- MA 色板：nous dark `5:#f6d365` `10:#ff8fab` `20:#b388ff` `30:#6ee7b7`（与下跌绿区分）`60:#4fc3f7`；其余组合沿用现有值，目检微调

### 10.5 Flat, not boxed 落地规则

1. **面板不嵌套**：无 card-in-card；分组靠留白 + 单条 hairline（`1px color-mix(currentColor 3–8%, transparent)`）
2. **浮动层专用**：菜单/抽屉/tooltip 用 `--ui-shadow-nous` + `--ui-stroke-nous`，不加重边框
3. **表格**：行分隔 hairline（stroke-tertiary），hover 用 `--ui-bg-subtle`；buy/sell/hold 语义行色保留（数据语义，非装饰）
4. **圆角**：全部走 `--ui-radius-scalar` 缩放，组件不写死 px
5. **组件变体**：Button 单一组件 + variant（default/secondary/ghost/outline/destructive），调用点不传 className 覆盖
6. **侧栏**：sidebar 底色（`--ui-bg-app` 或 panel 变体）+ 单条 hairline 分隔，不浮起不投影
7. 首页功能卡 `.card` 保留为入口卡片（导航用途，非嵌套面板）

### 10.6 落地文件清单

| 文件 | 改动 |
|---|---|
| `web/ui/src/index.css` | 重构 token 区：语义层 + 主题注册表值层（`[data-theme][data-mode]` 四组合），旧变量别名只在 `:root` 定义一次（惰性引用 `--ui-*`） |
| `web/ui/src/chart/theme.ts` | `THEMES: Record<ThemeId, Record<Mode, ThemePalette>>`，MA 色板按主题适配 |
| `web/ui/src/components/ThemeContext.tsx` | 扩展为 `{ themeId, mode }` 模型 + 持久化（兼容旧 key） |
| `web/ui/src/components/ThemeSwitcher.tsx`（新） | 顶栏主题按钮 + 弹出菜单（Nous Dark/Light · Belafonte Night/Day），浮动层规范 |
| `web/ui/src/components/Layout.tsx` | 侧栏/顶栏用语义 token；集成 ThemeSwitcher |
| 新组件 | 按变体规范建（Button 等，随功能页推进） |
| 本文档 | 本规范为唯一 UI token 事实源 |
