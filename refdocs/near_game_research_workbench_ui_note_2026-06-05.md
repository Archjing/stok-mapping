# 近游戏体验研究工作台 UI 主题研究 Note

> 日期：2026-06-05  
> 性质：主题研究 note / 头脑风暴归档  
> 状态：不落入当前项目开发计划  
> 主题：借鉴 Live2D、Notion、Obsidian 与游戏 UI，构建新型“近游戏体验”研究平台 UI 的未来可行性

---

可行，但要非常克制地做。这个方向适合做成“研究工作台的沉浸式交互层”，不适合做成“游戏化交易终端”。

核心判断：

| 方向 | 可行性 | 建议 |
| --- | --- | --- |
| Live2D 风格研究助手 | 高 | 可作为状态解释、报告导览、异常提示入口 |
| 类游戏任务流 | 中高 | 可用于数据治理、回填、策略准入 checklist |
| 沉浸式研究地图 | 中 | 适合展示数据源、因子、策略、报告之间的关系 |
| 游戏化交易反馈 | 低 | 不建议，容易强化冲动交易和错误激励 |
| 完整 2D 游戏壳 | 中低 | 成本高，ROI 不如先做轻量动效和交互层 |

## 推荐产品定位

不要叫“游戏化量化平台”，更合适的定位是：

> 本地优先的沉浸式量化研究工作台：把数据治理、策略验证、报告阅读、维护任务和模拟账户复盘，组织成类 Notion/Obsidian 的知识空间，并叠加轻量近游戏体验。

可借鉴的体验：

- Notion：块状信息、任务流、数据库视图、文档组织。
- Obsidian：本地 vault、双链、图谱、研究关系网络。
- Live2D：情绪化助手、状态反馈、报告导览。
- 游戏 UI：任务面板、状态 HUD、事件日志、场景化工作台。

## 推荐形态

比较合适的界面可以是：

- 左侧：研究空间导航，类似 Obsidian vault。
- 中间：报告、图表、策略准入卡片、维护任务看板。
- 右侧：Live2D / Rive 风格助手 + inspector。
- 底部：任务日志、backfill shard 状态、`db-health` 门禁事件。
- 全局：command palette，类似“运行 db-health”“打开最新报告”“恢复某个 shard”。

Live2D 助手的职责应该是：

- 解释当前系统状态。
- 提醒数据异常。
- 导航报告。
- 用自然语言总结 `db-health`、backfill、策略准入。
- 不直接给交易建议，不表达“买入/卖出”情绪。

## 技术路线

优先级建议：

1. `Tauri + Web 前端`

最适合本项目本地优先、SQLite、文件报告、CLI 编排器的形态。Tauri 官方定位就是用 Web 前端构建跨平台桌面应用，并可用 Rust 承接本地能力；它也有 capabilities/permissions 机制，适合限制前端访问本地资源。

2. `Rive`

更适合 UI 动效、状态机动画、轻量交互动效。Rive 官方 runtimes 支持 Web 等多平台，且官方文档说明 runtimes 是开源 MIT。适合做按钮、状态卡、任务进度、助手表情的轻量层。

3. `Live2D Cubism SDK for Web`

适合做角色型助手。Live2D 官方提供 Web SDK，源代码以 TypeScript 编写，可用于 Web/JS 生态。风险是模型制作成本、授权、性能和风格一致性。

4. `Electron`

作为备选。Electron 官方强调其嵌入 Chromium 和 Node.js，生态成熟、渲染一致性强，但更重。若未来复杂图表、插件生态、前端团队效率优先，可考虑。

## 架构建议

不要让 UI 直接操作数据库和策略模块。未来应保持：

```text
Near-game Desktop UI
    -> UI Command Broker
    -> maintenance_orchestrator / phase0 CLI
    -> SQLite / reports / logs
```

这样 UI 是体验层，不是事实来源。

## 最大风险

- 把金融研究做得太像游戏，会刺激错误交易心理。
- Live2D 角色如果过度“拟人化建议”，会弱化数据审计意识。
- 动效过多会降低高密度表格、审计报告、策略比较的效率。
- 角色资产、授权、动画制作成本可能高于前端开发本身。
- 本地 token、账户 CSV、日志路径必须做权限隔离。

## 建议的探索顺序

1. 先做 `UI-0` 概念原型：不接数据，只验证布局、动效密度和角色是否干扰研究。
2. 再做 `UI-1` 只读报告库：读取 `reports/`，像 Obsidian 一样组织报告。
3. 再做 `UI-2` 数据治理控制台：接 `db-health` 和 `T6.3 maintain status`。
4. 最后才考虑 Live2D 助手深度接入。

结论：这个方向有价值，但应该作为“研究体验层”而不是“交易游戏化”。最优切入点是 `T6.3` 维护编排器完成后，用 Tauri 做本地桌面壳，用 Rive 做轻量动效，Live2D 只作为可选的研究助手层。

---

## 补充：关注个股分析工具先做 TUI 的可行性

可行，而且比直接做桌面 UI 更适合作为第一版。

结论：**关注个股分析工具先做 TUI 很合适**。原因是本项目现在已经是 CLI / SQLite / reports 驱动，TUI 能复用现有能力，开发成本低，部署简单，不需要先搭 Tauri/Electron。

推荐形态：

```text
stock-focus tui
    左侧：关注股票列表 / 分组 / 状态
    中间：单股分析面板
    右侧：风险标签 / 数据质量 / 相关报告
    底部：命令栏 / 刷新状态 / 最近任务日志
```

适合在 TUI 里做的：

- 添加 / 删除 / 归档关注股票
- 查看关注列表
- 切换股票
- 查看行情摘要、估值、财务摘要、风险标签
- 打开最近单股评估报告路径
- 触发 `focus refresh`
- 查看数据质量和最近更新时间
- 以表格/小图形式展示趋势

不适合第一版 TUI 做的：

- 复杂 K 线交互
- 多图联动
- 高级拖拽布局
- 类 Notion/Obsidian 的复杂文档体验
- Live2D/Rive 这类动效

技术建议：

| 方案 | 推荐度 | 理由 |
| --- | --- | --- |
| Python `Textual` | 高 | 适合本项目 Python 栈，能做现代 TUI，支持表格、布局、快捷键、异步任务 |
| Python `Rich` 直接手写 | 中 | 简单报告展示可以，交互复杂后会吃力 |
| `urwid` / `prompt_toolkit` | 中低 | 可用，但现代感和开发效率不如 Textual |
| Go/Rust TUI | 低 | 生态好，但会引入新语言栈，不符合当前项目最小路径 |

最小 MVP：

- `phase0.cli focus tui`
- `phase0.cli focus add <symbol>`
- `phase0.cli focus list`
- `phase0.cli focus refresh <symbol>`
- 本地库：`data/stock_focus/stock_focus.sqlite`
- 报告输出：`reports/stock_focus/YYYY-MM-DD/<symbol>_focus_report.md`

TUI 第一版可以只显示：

- 关注股票列表
- 最新行情日期
- 最新收盘价 / 涨跌幅
- 估值字段
- 财务摘要
- 数据质量状态
- 风险标签
- 最近报告路径

架构上建议这样接：

```text
Textual TUI
    -> focus service
    -> local SQLite / a_share_history.sqlite / reports
    -> existing db-health / factor / account modules
```

建议：**TUI 是最优第一步，桌面 UI 是后续产品化形态。**

先用 TUI 把数据模型、单股分析口径、报告结构跑通，再决定是否迁移到 Tauri 桌面端。

## 参考来源

- Live2D Cubism SDK for Web: https://docs.live2d.com/en/cubism-sdk-manual/cubism-sdk-for-web/
- Live2D Cubism SDK: https://www.live2d.com/en/sdk/about/
- Rive Runtimes: https://rive.app/runtimes
- Tauri docs: https://tauri.app/start/
- Tauri capabilities: https://tauri.app/fr/security/capabilities/
- Electron docs: https://www.electronjs.org/
