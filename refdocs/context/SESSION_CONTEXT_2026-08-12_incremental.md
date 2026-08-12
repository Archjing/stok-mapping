# 2026-08-12 Session 增量工程归档

归档日期：2026-08-12
定位：记录 SOX + VIX 映射 A 股半导体 ETF 的 5 分钟级模拟账户能力、数据边界与可复现验证。

导航：[`refdocs 索引`](../README.md)

---

## 本轮工程决策

- 将原先仅面向 `SH.512480` 的策略统一为
  `cross_market_semiconductor_timing_etf_v1`。策略逻辑共用，模拟账户通过
  `accounts.simulated[].strategy_params.target_symbol` 独立指定 ETF。
- 每个账户保有独立的现金、持仓、成交、净值、账本和 SQLite 状态；策略参数在账户加载时复制，
  不会在账户间共享或污染。
- 标的采用 fail-closed 白名单：`SH.512480`、`SH.512760`、`SH.516920`、
  `SH.516640`、`SZ.159995`、`SZ.159813`、`SZ.159801`、`SH.588200`。清单外代码
  被策略配置校验拒绝。
- `semiconductor_timing` 账户仍指向 `SH.512480`。本轮不自动创建第二个真实模拟账户，
  也不把 512480 的回测或 admission 结论外推至其它 ETF。
- 新增 `semiconductor_timing_etfs` 手工 ETF universe，仅用于受控回填范围声明；声明标的
  不等于自动下载、5 分钟数据已完整，或允许启用模拟账户。
- 关键 5 分钟数据缺失必须阻断账户状态写入；不可将缺失解释为无信号或零交易。
- 移除了项目内 Windmill 专用说明和参考链接；当前调度由项目自身编排器负责，不依赖 Windmill。

## 验证证据

```bash
PYTHONPATH=. .venv/bin/python -m pytest -q \
  tests/test_cross_market_semiconductor_timing.py \
  tests/test_single_etf_intraday_execution.py \
  tests/test_cli_intraday_account.py \
  tests/test_execution_account_ledger.py \
  tests/test_etf_universe.py
# 42 passed

PYTHONPATH=. .venv/bin/python -m pytest -q
# 675 passed in 30.16s
```

配置解析也已验证：`semiconductor_timing` 使用
`cross_market_semiconductor_timing_etf_v1`，账户级参数为 `SH.512480`。

## 已知运行边界与后续事项

- 以 `--as-of 2026-08-11` 重放时，`semiconductor_timing` 的
  `simulation_start_date: 2026-08-12` 会令日期筛选后没有数据；这是账户生命周期起点晚于
  as-of 的配置边界，不是策略或 ETF 路由故障。
- 其它 ETF 启用前，必须逐只核验日线与 5 分钟线覆盖、新鲜度和会话完整性，并完成独立回测、
  walk-forward 与 admission。
- 当前 walk-forward 对跨市场 5 分钟策略仍需要后续架构演进：统一数据提供方、策略意图、
  执行结果和分组准入，避免将单 ETF 结果与股票池策略直接并列互选。
