# 2026-07-02 会话增量归档：多账户控制台账单与定时交付链路

## 背景

本轮围绕 `share.spidermanread.men/quant/` 多模拟账户静态控制台的账单语义、每日定时生成、上传和执行价入库时间做了排查与修订。用户明确要求：

- `/quant/accounts/default/latest/account-bill/` 不应显示“最新一次观察池运行里的待确认账单”，而应优先显示“最新已确认账单”。
- 页面应先查当天执行价是否入库；若当天账单已确认，显示当天账单；若未确认，则显示最近已确认交易日账单，并在页面开头说明原因。
- 需要确认 account-bill 每个交易日什么时间生成和上传，以及当天 A 股执行价什么时间下载入库。

## 关键结论

- 系统 cron 已安装，每分钟调用 `scripts/run_project_scheduler.sh`。
- 编排器 `daily_brief` 任务在中国 A 股交易日 `07:20` 运行：
  `phase0.cli brief watchlist --config config.yaml --all-accounts`
- `07:20` 任务生成当天盘前观察单，并更新/发布多账户 `/quant/` 控制台。
- `07:20` 不能确认当天账单；因为当天执行价 OHLCV 尚未入库。
- A 股日线和模拟交易执行价入库任务是 `a_share_history`，当前定时为交易日 `16:30`。
- 模拟账户执行价数据使用 `local_history.execution_adjust_type: bfq`，这是合理口径：真实成交应使用不复权价格，不应用前复权价成交。
- 模拟账户具体成交价字段由账户/执行层配置决定：
  - `accounts.simulated[].execution_price_mode`
  - fallback 到全局 `execution.price_mode`
  - 当前默认账户为 `next_open`
- `next_open` 用执行日开盘价，交易时间记为 `09:30`；`close` 用执行日收盘价，交易时间记为 `15:00`；`conservative` 在开盘价基础上做保守 buffer。
- 当前 `16:30` 只保证执行价入库，不等于账户账本已重算；若要盘后自动切到当天确认账单，后续应增加 `16:45` 或 `17:00` 的“账户账本重算 + site publish”任务。

## 本轮代码/配置变更

- `phase0/reporting/quant_static_site.py`
  - `/quant/accounts/<account>/latest/account-bill/` 改为优先显示当天已确认账单。
  - 若当天未确认，则显示最近已确认交易日账单。
  - 页面开头新增状态说明，区分：
    - 当天执行价未入库。
    - 当天执行价已入库但账户账本尚未确认。
    - 当天账单已确认。
- `phase0/reporting/account_bill.py`
  - `export_account_bill_html()` 增加 `status_message` 参数，用于在账单页开头显示状态说明。
- `config.yaml`
  - `manual_history_update.adjust_types` 从 `["qfq"]` 改为 `["qfq", "bfq"]`，保证定时 A 股日线更新会同步维护模拟执行价所需的 `bfq` 数据。
- `tests/test_quant_static_site.py`
  - 增加 `/quant/.../latest/account-bill/` 回退说明断言。
- `tests/test_maintenance_orchestrator.py`
  - 增加配置测试，确保 `execution_adjust_type: bfq` 时 `manual_history_update.adjust_types` 包含 `bfq`。
- `tests/test_cli_delivery_commands.py`
  - 补充 watchlist pipeline 与 `/quant/` 发布链路相关测试桩。

## 执行命令与验证

- 发布多账户静态控制台：
  `./runit site publish --config config.yaml`
- 远端核验：
  `https://share.spidermanread.men/quant/accounts/default/latest/account-bill/index.html`
- 当前远端页面状态说明已显示：
  `2026-07-02 的 bfq 执行价尚未入库。 当前展示最近已确认交易日 2026-07-01 的账单。`
- 测试：
  `TMPDIR=/tmp ./.venv/bin/python -m pytest -s -q tests/test_quant_static_site.py tests/test_account_bill_html.py tests/test_maintenance_orchestrator.py::test_manual_history_update_includes_bfq_execution_prices tests/test_cli_delivery_commands.py::test_watchlist_pipeline_updates_history_and_copies_latest`
- 结果：
  `9 passed, 1 warning`
- 静态检查：
  `git diff --check -- config.yaml phase0/reporting/account_bill.py phase0/reporting/quant_static_site.py tests/test_quant_static_site.py tests/test_maintenance_orchestrator.py tests/test_cli_delivery_commands.py`
- 结果：
  通过。
- 调度 dry-run：
  `./runit maintain tick --config config.yaml --as-of '2026-07-02 16:30' --dry-run`
- 结果：
  `a_share_history will_run at 16:30`。

## 当前状态与风险

- `/quant/.../latest/account-bill/` 已符合“最新已确认账单优先，当天未确认则说明并回退”的语义。
- A 股当天执行价下载时间为 `16:30`，这个时间适合作为盘后确认口径。
- 目前还没有单独的盘后账户账本重算任务；因此 `16:30` 后即使 `bfq` 执行价已入库，也需要后续任务重建账户账本并发布 `/quant/`，页面才会切换成当天已确认账单。

## 下一步建议

- 新增交易日 `16:45` 或 `17:00` 任务，例如 `account_bill_close_confirm`：
  - 不重新生成盘前观察单信号。
  - 使用已有 watchlist 与新入库的当天 `bfq` 执行价重建账户账本。
  - 重新 build/sync `/quant/`。
  - 在日志中记录本次确认账单日期、账户数和是否有未成交/部分成交。
