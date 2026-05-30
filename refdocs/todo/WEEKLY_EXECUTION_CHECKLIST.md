# 周执行计划总清单（开发计划书附件）

> 本文件是 `DEVELOPMENT_PLAN.md` 的统一周执行附件。  
> 后续每一周的任务清单都追加在同一个文件中，避免多个附件分散。  
> 主计划中的长期路线、阶段划分和项目定位以 `DEVELOPMENT_PLAN.md` 为准；本文件只管理**当前周目标、执行节奏、检查点与归档要求**。

---

# Week 1｜本土主策略候选验证（已完成并归档）

## 1. 本周目标

> 在现有 compare / report / gate 链路下，验证 A 股本土候选策略，修正候选比较口径，并判断当前失败到底来自策略逻辑、参数、样本治理还是交易成本。

## 2. 当前基线与门槛缺口

### 当前基线
- 当前 selected candidate：`legacy_momentum_low_turnover_v1`
- 当前 gate：`PASS`
- 当前口径：portfolio-scope
- 当前样本：7 年窗口，4 个 portfolio fold

### 当前缺口
- 当前 gate 已无硬性缺口
- `annualized_return_mean = 0.1440`
- `sharpe_mean = 1.0886`
- `max_drawdown_mean = -0.1012`
- `win_rate_mean = 0.5129`

### 当前判断
- 低换手改造已经替代旧 `legacy_momentum` 成为当前主候选。
- 当前主要工作从“修复 Sharpe”切换为“收口解释链路、补齐账户仿真约束、接入日常输出”。
- 成本敏感性显示新候选在 `current_cost` 下已可通过 gate，后续不需要再靠零成本结论证明有效。

## 3. 本周候选范围

### 候选 1：MA/K 线低复杂度 baseline
- [x] 建立低复杂度、可解释、可复现的技术基线
- [x] 作为本周的诊断地板
- [x] 结论：current-cost 下表现弱，不作为下一轮主攻方向

### 候选 2：短周期残差动量 + 反转增强 v2
- [x] 在已有 `residual_momentum_reversal_v1` 基础上最小增强
- [x] 完成 portfolio compare
- [x] 已降级为备选，只在主线收口后再考虑低换手版本

### 候选 3：多因子 + 量价二次筛选 v1
- [x] 作为本周最重要的冲门槛候选
- [x] 用更完整的本土特征组合争取超过 `legacy_momentum`
- [x] 已完成 32 季度财务因子覆盖后的 portfolio compare
- [x] 已确认 current-cost 下不胜出，暂不继续占用主线

### 本周新增治理/框架修复
- [x] 将 `legacy_momentum` 从 symbol-scope 改为 portfolio-scope baseline
- [x] 将回测窗口从 `5` 年扩大到 `7` 年
- [x] 将财务因子维护窗口从 `8` 季度扩大到 `32` 季度
- [x] 新增成本敏感性报告：`current_cost` / `low_slippage` / `zero_cost`
- [x] 修复 point-in-time 财务因子 merge 的 datetime dtype 边界
- [x] 更新 `README.md`、`DEVELOPMENT_PLAN.md`、`reports/phase0_strategy_change_log.md`

## 3.5 数据源升级准备项（仅准备，不实施）

> 目的：为 Week 2 的 FRED / Tiingo 数据源升级做口径确认，不改变当前 Week 1 以策略验证为主的顺序。

- [ ] 确认 `FRED` 首批序列清单：`GDP`、`CPIAUCSL`、`FEDFUNDS`、`DFF`、`VIXCLS`
- [ ] 确认 `Tiingo` 首批标的清单：`NVDA`、`AAPL`、`TSLA`、`KWEB`
- [x] 确认 `yfinance` 在过渡期继续保留为 fallback
- [x] 确认 Week 1 已按治理需要修改 `phase0` 正式回测链路，并完成报告/变更日志同步
- [x] 把 US/HK market history 和 yfinance fallback 结论写入变更日志和主计划书

## 3.6 策略积木迭代（主线工程增强）

> 目的：把当前“配置参数 + 代码里写死的候选实现”升级为“可插拔策略模块”，从而让新策略更快接入、更快测试、更快输出统一报告，并为后续策略选定后的研判简报与模拟交易预留统一接口。

参考文档：`refdocs/todo/策略积木.md`

- [x] 设计最小策略契约：策略元信息、输入声明、参数选择/拟合、信号/排序输出、说明文本
- [x] 建立 `phase0/strategies/` 目录与 `base.py` / `registry.py` 雏形
- [x] 先迁移 `legacy_momentum` 到策略模块
- [x] 再迁移 `residual_momentum_reversal_v1` 到策略模块
- [x] 让 compare 候选从 registry + config 生成，而不是只在 `_run_compare` 里手工拼装
- [x] 统一策略摘要输出格式，确保继续兼容现有 report/csv 体系
- [x] 预留“选定策略 → 研判简报 / 模拟交易”所需的标准化 signal/weight 输出接口

## 4. 推荐执行顺序

### 研究优先级
1. 低换手 legacy momentum 改造
2. 账单 / 资产轨迹 / 买卖原因导出
3. 账户级仿真与实盘约束补齐

### 实现顺序
1. **低换手 / 延长持有 baseline**
2. **账单 / HTML 预览 / 日资产导出**
3. **账户级仿真与解释链路收口**

### 原因
- [x] 原 baseline 已落地并证明 MA/K 线 current-cost 表现弱
- [x] residual v2 可复用现有实现，但成本敏感性偏高
- [x] multifactor v1 已进入 compare，但 current-cost 下仍不胜出
- [x] 当前不再优先加因子复杂度，先完成低换手策略收口与执行约束

## 5. Day 1 - Day 7 节奏

### Day 1：统一共享特征与候选比较口径
- [x] 让候选在同一条 compare / report / gate 链路里比较
- [x] 共享价格 / 量能特征可复用
- [x] 候选比较报告更清晰
- [x] 已统一为 portfolio-scope 比较

### Day 2：完成 MA/K 线 baseline
- [x] 形成第一个低复杂度 compare-only 候选
- [x] `ma_kline_baseline_v1` 进入 compare 结果
- [x] 作为诊断地板保留
- [x] 结论：current-cost 下不适合作为主候选

### Day 3-4：完成 residual momentum + reversal v2
- [x] 复用现有残差动量候选，做最小增强
- [x] `residual_momentum_reversal_v2` 进入 compare
- [x] 完成成本敏感性观察
- [ ] 下一轮只研究低换手/持有期约束版本

### Day 5-6：完成 multifactor + volume/price filter v1
- [x] 作为本周最强候选，尝试直接改善主 gate
- [x] `multifactor_volume_price_filter_v1` 进入 compare
- [x] 已在 32 季度财务因子下重跑
- [ ] current-cost 下未优于 `legacy_momentum`，下一轮需要先做成本约束

### Day 7：统一 compare、决策、归档
- [x] 更新 compare 结果
- [x] 更新 effectiveness report
- [x] 更新 change log
- [x] 明确每个候选是保留、淘汰还是晋级

## 6. 本周比较与归档要求

- [x] 记录候选名称
- [x] 记录变更原因
- [x] 记录参数或规则摘要
- [x] 记录最新回测结果摘要
- [x] 记录是否保留
- [x] 记录是否晋级
- [x] 记录下一步建议

归档位置：
- [x] `reports/phase0_walk_forward_report.md`
- [x] `reports/phase0_effectiveness_report.md`
- [x] `reports/phase0_walk_forward_candidates.csv`
- [x] `reports/phase0_strategy_change_log.md`
- [x] `reports/phase0_cost_sensitivity_report.md`

## 7. 本周成功标准

### 硬门槛
- [x] compare mode 中出现一个不是 `legacy_momentum` 的新优胜候选
- [x] `annualized_return_mean > 0`
- [x] `sharpe_mean > 0.5`
- [x] `max_drawdown_mean > -0.25`
- [x] `win_rate_mean > 0.45`
- [x] `oos_return_decay_ratio < 0.30`

### 软判断
- [x] 新候选显著改善当前失败项（Sharpe）
- [x] 结果不是由少数 fold 偶然支撑
- [x] 候选逻辑可解释、可延续、可复盘
- [x] 成本敏感性已可解释

## 8. 本周不做事项

- [ ] 不重开跨市场主 ranker 路线
- [ ] 不把跨市场映射重新作为主选股核心
- [ ] 不推进 Web / PWA / App / Dashboard
- [ ] 不推进自动交易与下单执行
- [ ] 不让 LLM 直接生成交易信号
- [ ] 不大规模重构基础设施
- [ ] 不修改 universe 主评分逻辑，除非本周结果明确要求下一轮再做

## 9. 本周结束后的决策规则

### 如果有候选通过 gate
- [x] 提升为新的主候选
- [x] 在变更日志中记录晋级原因
- [x] 进入下一轮更细的参数与稳定性验证

### 如果没有候选通过 gate
- [ ] 保留 `ma_kline_baseline_v1` 作为诊断地板
- [ ] 保留 `legacy_momentum` 作为 portfolio baseline
- [ ] 在 residual / multifactor 中只保留低换手改造版本继续 compare
- [ ] 下一轮重点转向：**持有期、换手、滑点敏感性控制**，而不是继续加大因子复杂度

---

# Week 1.5｜Sharpe 修复与成本敏感性收敛

## 1. 本周目标

- [x] 在 current-cost 假设下将 selected candidate 的 `sharpe_mean` 提升到 `> 0.5`
- [x] 保持 `max_drawdown_mean > -0.25`
- [x] 保持 `win_rate_mean > 0.45`
- [x] 降低 current-cost 与 low-slippage 场景之间的表现差距

## 2. 当前基线

- selected candidate：`legacy_momentum_low_turnover_v1`
- annualized_return_mean：`0.1440`
- sharpe_mean：`1.0886`
- max_drawdown_mean：`-0.1012`
- win_rate_mean：`0.5129`
- turnover_annual_mean：`1.50`
- low_slippage Sharpe：`1.0094`
- zero_cost Sharpe：`0.8371`

## 3. 优先实验方向

### 3.1 低换手 legacy momentum
- [x] 增加最小持有期约束
- [x] 增加换手惩罚或 trade cooldown
- [x] 测试更宽组合与更慢调仓，降低单票波动
- [x] 在参数选择阶段加入 cost-aware score

### 3.2 residual momentum 低换手版本
- [ ] 降低交易频率
- [ ] 避免短周期反转信号导致频繁换仓
- [x] 已确认不进入当前主线，只保留为后续备选

### 3.3 multifactor slippage-aware 版本
- [ ] 对 `amount_ratio20`、波动率、上影线等交易质量过滤重新设定
- [ ] 增加持有期或调仓频率限制
- [x] 已确认 current-cost 下未胜出，暂不继续占用当前主线

## 4. 验收要求

- [x] 每次策略逻辑或参数修改都写明理由和参考依据
- [x] 每轮都输出 current / low_slippage / zero_cost 三档成本敏感性
- [x] 不用零成本结果替代 current-cost gate
- [x] 不因单个 fold 表现好直接晋级
- [x] 变更写入 `reports/phase0_strategy_change_log.md`

---

# Week 1.6｜通过后收口与下一步开发

## 1. 本周目标

- [x] 跑完整 Phase 0，正式确认 `legacy_momentum_low_turnover_v1` 替代旧 `legacy_momentum`
- [x] 生成低换手策略账单 CSV、资产日表与 HTML 预览
- [x] 在账单中补充卖出原因、买入驱动力和中间年份折叠预览
- [x] 在通过策略与回测代码补充中文注释，解释模拟了什么看盘、研判和交易行为
- [ ] 将账单导出纳入标准 CLI / report 链路
- [ ] 在账户仿真中补齐 A 股整手成交、现金约束和撮合细节
- [ ] 完成财务因子公告日 point-in-time 校验方案
- [ ] 将当前 selected strategy 接入 `07:30` 盘前日报 / 观察池输出

## 2. 当前状态

- [x] 当前 selected candidate：`legacy_momentum_low_turnover_v1`
- [x] current-cost gate：PASS
- [x] 账单导出脚本：`scripts/export_low_turnover_bill.py`
- [x] 预览产物：`reports/phase0_low_turnover_bill_preview.html`
- [x] 日资产产物：`reports/phase0_low_turnover_daily_assets.csv`

## 3. 下一步实际编码顺序

- [ ] 先把账单导出接入正式命令入口，避免每次靠单独脚本调用
- [ ] 再补账户级交易约束，优先 A 股 `100` 股 / `1` 手整手买入与现金检查
- [ ] 然后做公告日 PTI 校验，给质量成长类候选扫清后续回测前提
- [ ] 最后把 selected strategy 输出接入日报 / 观察池

---

# Week 2｜数据源升级（FRED / Tiingo 分层替换）

## 1. 本周目标

- [ ] 明确形成项目级结论：**FRED 先、Tiingo 后、yfinance 保留 fallback**
- [ ] 完成第二周文档、边界和接入设计准备
- [ ] 为下一周正式编码实施做好输入条件

## 2. 当前基线确认

- [ ] A 股盘后主源仍是 `Tushare Pro`
- [ ] A 股 fallback 仍是本地 SQLite / AkShare / 新浪原始快照
- [ ] 美股 / ETF / VIX / CNH 当前已落库到 `us_market_history.sqlite`，过渡 provider 仍为 `yfinance`
- [ ] 宏观 / 利率当前尚未拆独立主源
- [ ] 当前第二周工作**不修改** `phase0` 主回测逻辑

## 3. 数据源分层结论

### 3.1 FRED 接管范围
- [ ] GDP → `GDP`
- [ ] CPI → `CPIAUCSL`
- [ ] 联邦基金利率（月）→ `FEDFUNDS`
- [ ] 联邦基金利率（日）→ `DFF`
- [ ] VIX → `VIXCLS`

### 3.2 Tiingo 接管范围
- [ ] `NVDA`
- [ ] `AAPL`
- [ ] `TSLA`
- [ ] `KWEB`

### 3.3 暂不处理范围
- [ ] CNH / FX 主源替换
- [ ] 所有美股指数一次性替换
- [ ] 当前 A 股正式主链路改造
- [ ] 直接移除 `yfinance`

## 4. FRED 接入任务

### 4.1 文档与映射
- [ ] 形成 FRED 序列映射表
- [ ] 每个序列都能映射到项目中的明确用途：
  - [ ] 风险解释层
  - [ ] 宏观 overlay
  - [ ] 日报结构化摘要输入

### 4.2 代码设计准备
- [ ] 明确 FRED adapter 入口
- [ ] 明确 FRED 数据缓存策略
- [ ] 明确 FRED 对 `config.yaml` 的新增配置项
- [ ] 明确 FRED 与现有 `yfinance` 的职责边界

### 4.3 验收
- [ ] FRED 引入不会破坏当前 `phase0.cli` 正式链路
- [ ] FRED 仅承接宏观 / 利率 / VIX，不与美股个股职责混淆

## 5. Tiingo 接入任务

### 5.1 覆盖范围确认
- [ ] 明确首批接入标的：`NVDA` / `AAPL` / `TSLA` / `KWEB`
- [ ] 明确这些标的在项目中的用途：
  - [ ] 美股日线
  - [ ] 产业映射核心触发标的
  - [ ] 隔夜解释层输入

### 5.2 代码设计准备
- [ ] 明确 Tiingo adapter 入口
- [ ] 明确 Tiingo 与 `yfinance` fallback 关系
- [ ] 明确 Tiingo 对 `config.yaml` 的新增配置项
- [ ] 明确 Tiingo 不处理宏观序列

### 5.3 验收
- [ ] Tiingo 只替换最关键的美股个股 / ETF，不扩大范围
- [ ] `yfinance` 仍保留为 fallback

## 6. 配置层重构草案

- [ ] 宏观、利率、VIX、个股、ETF、FX 的配置职责清晰拆分
- [ ] `tushare`：A 股盘后主源
- [ ] `fred`：宏观 / 利率 / VIX
- [ ] `tiingo`：美股个股 / ETF / EOD
- [ ] `yfinance`：fallback / FX 代理 / 临时研究源

## 7. 本周归档要求

- [ ] `yfinance` 当前保留职责
- [ ] `FRED` 建议接管的宏观 / 利率序列
- [ ] `Tiingo` 建议接管的美股标的范围
- [ ] 暂不替换的数据范围
- [ ] `config.yaml` 的目标重构方向
- [ ] 下一步实际编码顺序

归档位置：
- [ ] `DEVELOPMENT_PLAN.md`
- [ ] `reports/phase0_strategy_change_log.md`
- [ ] 本附件

## 8. 本周成功标准

### 硬门槛
- [ ] 明确形成“FRED 先、Tiingo 后、yfinance 保留 fallback”的项目级结论
- [ ] 明确 FRED 的首批序列清单
- [ ] 明确 Tiingo 的首批标的清单
- [ ] 明确哪些数据源不在本周替换范围内
- [ ] 明确下一步实施顺序：**先实现 FRED，再实现 Tiingo**

### 软判断
- [ ] 数据源职责边界清楚
- [ ] 不与当前正式链路冲突
- [ ] 不引入一次性大替换风险
- [ ] 文档口径统一

## 9. 本周不做事项

- [ ] 不重写 `phase0` 回测逻辑
- [ ] 不改当前 A 股 Tushare 主链路
- [ ] 不直接移除 `yfinance`
- [ ] 不把 FRED / Tiingo 一起一次性硬切进生产链路
- [ ] 不处理 CNH / FX 主源替换
- [ ] 不推进前端 / PWA / agent 自动化扩展

## 10. 本周结束后的分流

### 如果本周方案成熟
- [ ] 下一周进入 **FRED 实现周**
- [ ] FRED 稳定后再进入 **Tiingo 接入周**

### 如果本周方案不充分
- [ ] 继续保持 `yfinance` 不动
- [ ] 先补完 FRED 序列定义和用途口径
- [ ] 推迟 Tiingo 实现

---

## 结尾提醒

> 统一附件的目的不是增加文档数量，而是把“当前周”和“后续周”都放进同一个执行清单里，保持项目附件简洁、高效、连续可维护。
