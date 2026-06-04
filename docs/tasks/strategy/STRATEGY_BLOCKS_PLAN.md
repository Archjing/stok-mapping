# T2.3｜策略积木迭代开发计划

> 目标：把当前“**配置参数 + 代码里写死的候选实现**”升级为“**可插拔策略模块**”，让不同策略能够像积木一样快速接入、统一测试、自动输出报告，并支持用户后续选择策略进入研判简报乃至模拟交易。
>
> 本文档是对以下现有规划的迭代补充：
> - `docs/DEVELOPMENT_PLAN.md`
> - `docs/tasks/WEEKLY_EXECUTION_CHECKLIST.md`
>
> 定位：**主线计划内的工程化增强项**，服务于“更快形成可应用产品”，不是纯平台化重写。
>
> 父级计划：[`DEVELOPMENT_PLAN.md`](../../DEVELOPMENT_PLAN.md)  
> 任务索引：[`docs/tasks/README.md`](../README.md)

---

## T2.3.1 为什么现在做

当前策略表达方式是：

- 参数在 `config.yaml`
- 候选逻辑写死在 `phase0/walk_forward.py`
- 候选集合在 `_run_compare` 里手工组装
- 新增策略通常要同时改：配置、策略函数、compare 集合、报告口径

这会带来几个问题：

1. 新策略接入成本高
2. 不同策略实现风格不统一，比较成本高
3. 报告输出依赖人工拼装，难以规模化试验
4. 策略不能自然过渡到“选定策略 → 研判简报 → 模拟交易”链路
5. `walk_forward.py` 继续膨胀，后续维护风险越来越大

所以“策略积木”要解决的不是学术问题，而是一个非常实际的产品效率问题：

> **如何让新策略更快接入、更快测试、更快形成结论，并更容易进入后续应用链路。**

---

## T2.3.2 本次迭代的目标

本次迭代不追求一步到位做完整平台，而是完成以下目标：

### T2.3.2.1 主目标

把策略从“写死在回测文件里的函数集合”，升级为“统一契约下的可插拔模块”。

### T2.3.2.2 直接收益

完成后应具备这些能力：

- 新增一个策略时，不必修改大段 compare 主流程
- 不同策略能被统一发现、统一运行、统一评估、统一输出报告
- 用户可以根据 compare 结果选定某一策略，继续生成研判简报
- 后续模拟交易模块可以面向统一策略接口接入，而不用为每个策略单独适配

### T2.3.2.3 本次不做

本次迭代**不**做：

- 完整账户级模拟交易系统
- 大规模机器学习训练框架
- 前端界面重构
- 完整插件市场式动态加载系统

本次只做“策略接口标准化 + 策略注册机制 + 统一实验流水线入口”的第一版。

---

## T2.3.3 目标设计原则

### T2.3.3.1 插件优先，兼容当前主线

要支持新的策略模块化，但不能破坏当前：

- Phase 0 可运行链路
- compare / gate / report 输出
- 当前本土主因子主线

### T2.3.3.2 统一契约，策略只关心策略本身

通用逻辑应抽离到公共层：

- 数据加载
- 特征准备
- walk-forward 切分
- 指标计算
- 报告输出
- 候选汇总

策略模块本身只负责：

- 说明自己需要什么输入
- 定义自己的信号或排序逻辑
- 输出统一格式结果

### T2.3.3.3 先支持“快速试策略”，再考虑“完美平台化”

也就是说，先做：

- 注册新策略
- 自动跑 compare
- 自动出报告

再考虑后面的：

- 组合权重
- 账户仿真
- 高级注册表

---

## T2.3.4 目标架构

建议引入一层轻量策略模块结构：

```text
phase0/
  strategies/
    __init__.py
    base.py
    registry.py
    legacy_momentum.py
    residual_momentum_reversal.py
    quality_growth_price.py
    ma_kline_baseline.py
    multifactor_volume_price.py
```

### T2.3.4.1 核心组件

#### A. Strategy Base Contract
定义所有策略共同接口。

例如一版最小契约可以是：

- `strategy_id`
- `display_name`
- `prepare_features(panel, config)`
- `fit(train_panel, config)` 或 `select_params(train_panel, config)`
- `predict(valid_panel, fitted, config)`
- `build_positions(prediction, config)`
- `describe(params)`

#### B. Strategy Registry
负责：

- 注册策略
- 枚举可用策略
- 根据配置或 CLI 选择策略
- 统一生成 compare 候选列表

#### C. Experiment Runner
负责：

- 统一 walk-forward 调度
- 调用策略模块
- 收集统一指标
- 输出 folds / candidates / summary

#### D. Report Adapter
负责：

- 把不同策略输出适配成统一 report 行格式
- 自动写入 candidates compare 结果
- 自动生成“选中策略说明”

---

## T2.3.5 推荐的最小策略接口

建议第一版不要设计过重，先采用“够用”的接口：

### T2.3.5.1 元信息

每个策略模块定义：

- `strategy_id`
- `display_name`
- `category`：如 `rule_based / factor / ml`
- `supports_compare`
- `supports_brief`
- `supports_paper_trade`

### T2.3.5.2 输入声明

每个策略声明自己需要：

- 哪些特征列
- 是否需要跨市场 overlay
- 是否需要财务因子
- 是否需要行业信息
- 是否需要标签或训练阶段

### T2.3.5.3 统一输出

每个策略输出至少包括：

- 每日 signal / score / rank / weight 或 exposure
- 参数描述字符串
- fold 指标
- 候选摘要字段

### T2.3.5.4 为什么这样设计

这样就能把“如何运行策略”从“策略本体”里抽出来。

新增策略时，开发者主要做的是：

1. 新建一个模块
2. 实现约定方法
3. 在 registry 注册
4. 可选补一个默认配置段

而不是去修改 `walk_forward.py` 中多处代码。

---

## T2.3.6 与当前配置体系如何衔接

当前 `config.yaml` 不需要推倒重来，但需要增加一层更清晰的组织方式。

建议逐步过渡到：

```yaml
phase0:
  walk_forward:
    active_strategy: legacy_momentum
    compare_strategies:
      - legacy_momentum
      - residual_momentum_reversal_v1
      - ma_kline_baseline_v1
    strategy_registry:
      enabled: true
    strategies:
      legacy_momentum:
        ...
      residual_momentum_reversal_v1:
        ...
      ma_kline_baseline_v1:
        ...
```

### 当前兼容原则

- 旧的 `strategy_v2` 参数段先保留
- 新策略逐步迁移到 `strategies.<id>` 下
- compare 默认先兼容旧逻辑，再切换到 registry 逻辑

---

## T2.3.7 对 `walk_forward.py` 的重构方向

本次不要求把 `walk_forward.py` 完全拆空，但应先完成第一步收缩。

### T2.3.7.1 先抽离的内容

优先抽走：

- 策略 apply/select/run 逻辑
- candidate 注册集合
- 参数描述格式化逻辑

### T2.3.7.2 `walk_forward.py` 保留职责

短期内让它更多像一个 runner：

- 组织 panel
- 做 fold 切分
- 调 registry 拿策略
- 汇总指标
- 输出结果

### T2.3.7.3 这样做的好处

- 保持当前链路可运行
- 避免一次性重构太大
- 新策略可以先模块化落地
- 老策略可以渐进迁移

---

## T2.3.8 对报告与结论输出的要求

“策略积木”不是只为了好看，必须直接改善报告产出效率。

### T2.3.8.1 统一 compare 输出

每个策略都应自动生成：

- 候选名称
- 参数摘要
- 年化收益
- Sharpe
- 最大回撤
- 胜率
- 换手
- 是否晋级建议

### T2.3.8.2 支持策略选择后继续输出

当 compare 选出一个候选后，应支持：

- 生成该策略的研判简报输入
- 输出该策略的观察池解释
- 保留该策略进入后续模拟交易的统一接口

### T2.3.8.3 未来可衔接模拟交易

本次不做模拟交易，但接口应预留：

- `supports_paper_trade`
- 标准化 signal / weight 输出

这样未来用户选择策略后，可以直接挂到 paper-trade runner 上。

---

## T2.3.9 建议的实施步骤

### T2.3.9.1 建立基础契约与注册表

目标：让策略可以被“声明式注册”。

任务：
- 新建 `phase0/strategies/base.py`
- 新建 `phase0/strategies/registry.py`
- 定义最小策略协议
- 实现 registry 的 register/list/get

### T2.3.9.2 先迁移 2 个现有策略

目标：验证积木思路是否成立。

优先迁移：
- `legacy_momentum`
- `residual_momentum_reversal_v1`

原因：
- 一个是当前 baseline
- 一个是本土主线增强候选

### T2.3.9.3 让 compare 走 registry

目标：不再在 `_run_compare` 里手工写候选集合。

做法：
- compare 从配置读取 strategy ids
- registry 返回对应策略模块
- runner 统一执行

### T2.3.9.4 统一报告适配

目标：让所有策略自动产出统一摘要。

做法：
- 规范 candidate summary row
- 规范 selected_params / describe 输出
- 规范 compare report 行格式

### T2.3.9.5 加入新策略模板

目标：让后续新增策略像搭积木。

做法：
- 提供策略模板文件
- 提供接入 checklist
- 让 `ma_kline_baseline_v1` 或 `multifactor_volume_price_filter_v1` 按新模板接入

---

## T2.3.10 验收标准

本次“策略积木”迭代完成后，至少应满足：

### 功能验收

- 新增策略无需直接改 `walk_forward.py` 大段 compare 逻辑
- 至少 2 个现有策略完成模块化迁移
- compare 候选可通过 registry + config 组合生成
- 候选结果仍能输出到现有 report/csv 体系

### 工程验收

- `walk_forward.py` 中候选硬编码明显减少
- 策略模块结构清晰
- 新策略接入路径可复用

### 产品验收

- 用户后续可以根据 compare 结论选择策略
- 被选中策略可以更容易进入研判简报链路
- 为未来模拟交易接口打下统一输入基础

---

## T2.3.11 本次迭代与主线计划的关系

这是一个**主线内的工程效率增强迭代**，不是远期展望。

它直接服务于当前主线目标：

- 更快测试新策略
- 更快形成结论
- 更快进入观察池和研判输出

因此它应该被纳入：

- `DEVELOPMENT_PLAN.md` 的当前产品主线语境
- `docs/tasks/WEEKLY_EXECUTION_CHECKLIST.md` 的近期执行任务

而不是放到 `refdocs/OUTLOOK/` 中等待远期处理。

---

## T2.3.12 一句话总结

> “策略积木”迭代的本质，是把当前项目从“新增一个策略要改很多地方”，升级到“新增一个策略只需实现统一接口并注册”，从而让策略测试、报告生成、结论输出和后续应用衔接变得像搭积木一样高效。
