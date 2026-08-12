<div align="center">
<img src="./assets/brand/stok-mapping-wordmark.png" width="90%" alt="stok-mapping">
</div>

# stok-mapping

本地优先的 A 股量化研究、跨市场映射分析和模拟执行系统。

项目以 A 股本土因子研究为主，以海外市场风险与情绪信息为辅。它把数据同步、可追溯的本地历史库、策略验证、模拟账户和盘前观察页串成一条研究链路；它**不是**券商交易系统，也不会自动下单。

```text
外部数据源
    ↓
本地 SQLite 历史库与审计
    ↓
股票池 / 特征 / 跨市场信号
    ↓
组合策略 walk-forward 或单 ETF 5 分钟模拟执行
    ↓
准入报告、模拟账本、盘前观察池与静态站点
```

项目根目录的 `./runit` 等价于 `./.venv/bin/python -m phase0.cli`。模块与命令目前仍使用 `phase0` 名称；迁移到 `quant` 是计划中的重命名，尚未实施。

## 当前能力（2026-08-12）

- A 股主库：`data/a_share_history.sqlite`，提供日线、复权因子、财务因子、交易日历和 point-in-time 研究读取。
- ETF 独立库：`data/etf_history.sqlite`，提供受控 ETF 目录、可恢复日线/复权回填、5 分钟线和开盘快照；数据和审计产物均为 local-only。
- 跨市场库：`data/us_market_history.sqlite` 与 `data/hk_market_history.sqlite`。US 库按自动信号、半导体广度、大型科技 beta、利率、中国科技情绪和参考/汇率分组维护。
- 组合策略研究：股票池、walk-forward、compare、执行诊断、过拟合诊断和 strategy-admission 仍是 A 股组合策略的主验证链路。
- 专用单 ETF 模拟：`cross_market_semiconductor_timing_etf_v1` 使用已完成的 `^SOX` / `^VIX` 美股日信号，映射到下一个 A 股交易日；账户以 5 分钟数据执行入场、追踪止损和收盘退出。
- 盘前交付：半导体 ETF 账户页显示 SOX/VIX、`us_market_news` 新闻元数据和账户账本；静态站点可本地构建并同步到受限的 `/quant/` 远端目录。
- 研究原型：`CN_PANIC_HO30` 已有上证 50 股指期权 VIX 方法论脚本和本地研究库写入能力，但尚未接入配置、CLI、调度、正式数据治理或交易过滤器。

### 当前策略边界

`baseline_admission_all_v1` 当前配置有 14 个注册条目：既包括可横向比较的组合策略，也包括一个使用专用数据/执行模型的单 ETF 跨市场策略。因此不能把它们混作同一张可比的 admission 排名表。

严格 `qfq_asof`、PIT 股票池、成本和执行约束下，组合策略目前没有已批准进入 paper review 或实盘模拟的候选。半导体 ETF 策略已具备**专用模拟执行**能力，但仍需为每一个目标 ETF 独立完成历史覆盖、回测、walk-forward 和 admission；`SH.512480` 的研究结果不能外推到其他 ETF。

## 常用命令

```bash
# 查看所有当前 CLI 命令
./runit --help

# 维护本地历史库
./runit update-history --config config.yaml
./runit update-us-market-history --config config.yaml
./runit update-hk-market-history --config config.yaml
./runit update-financials --config config.yaml

# ETF：先查看受控范围，再执行可恢复回填
./runit resolve-etf-universe --config config.yaml \
  --universe semiconductor_timing_etfs --start-date 2021-01-01 --end-date 2026-08-12
./runit backfill-etf-history --config config.yaml \
  --universe single_etf --sector semiconductor --start-date 2019-06-12 --end-date 2026-08-12 --dry-run

# 组合策略研究与数据门禁
./runit db-health --config config.yaml --scope cn --fail-on error
./runit strategy-admission --config config.yaml \
  --presets baseline_2y_1y_5fold --strategy-set baseline_admission_all_v1

# 单 ETF 模拟账户：默认只读重放；--recover-missing 仅用于盘后核验/恢复
./runit intraday-account --account-id semiconductor_timing --as-of 2026-08-12
./runit intraday-account --account-id semiconductor_timing --as-of 2026-08-12 --recover-missing

# 静态站点
./runit site build --config config.yaml
./runit site publish --config config.yaml
```

`intraday-account --recover-missing` 不是实时执行器：它只在盘后针对指定日期核验或补齐缺失产物；若现有实时产物与完整分钟线重放不一致，会失败而不会静默覆盖账本。

## 数据与信号口径

| 范围 | 本地资产 | 用途与边界 |
| --- | --- | --- |
| A 股 | `data/a_share_history.sqlite` | `qfq_asof` 仅用于研究读取；原始价格服务交易执行语义。 |
| ETF | `data/etf_history.sqlite` | 日线、复权、5 分钟与开盘快照；只允许配置声明的 universe/sector 或 `single_etf`。 |
| US | `data/us_market_history.sqlite` | `core_signal`（`^SOX`、`^VIX`）是当前半导体 ETF 策略唯一自动输入；其余分组仅供研究与观察。 |
| 新闻 | `data/ai_corpus/ai_corpus.sqlite` | `us_market_news` 用于盘前人工研判，不改变自动信号、仓位或订单。 |
| 模拟账本 | `data/simulated_trading/` | 账户、日资产、成交、订单事件和运行状态；不上传到 Git 或静态站点。 |

价格、复权、as-of、数据覆盖和回填审计规则见 [数据资产说明](data/README.md)。

## 文档入口

- [架构说明](docs/PROJECT_ARCHITECTURE_OVERVIEW.md)：模块边界、数据流、账户执行和运维边界。
- [开发计划](docs/DEVELOPMENT_PLAN.md)：完成项、当前优先级、验收门槛和技术债。
- [编码规范](docs/CODING_STYLE_RULES.md)：Python、数据、策略、测试和配置的工程约束。
- [CLI 使用说明](docs/PHASE0_CLI_USER_GUIDE.md)：当前命令、参数和站点发布配置。
- [策略研发规范](docs/STRATEGY_DEVELOPMENT_GUIDELINES.md)：策略从假设到 admission 的最小研发流程。
- [文档索引](docs/README.md)：现行文档、策略说明与历史归档的边界。

## 非目标与安全边界

- 不接券商 API，不自动下单，也不将新闻或 LLM 输出直接转成交易指令。
- 不在策略运行时临时请求网络行情；研究与报告优先读取已落库、可审计的数据。
- SQLite、报告、日志、新闻原文和账户账本均是本地运行资产，默认不进入 Git 或静态站点。
- token、服务器密码和远端地址只通过 `.env` 注入；禁止提交到配置、报告、日志或命令行参数。
- Yahoo/yfinance 限流、第三方权限不足和分钟数据缺失都必须以明确的失败、降级或审计状态呈现，不能把旧数据伪装为最新数据。
