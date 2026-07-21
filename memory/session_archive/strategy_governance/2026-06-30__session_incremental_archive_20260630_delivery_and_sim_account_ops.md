# 2026-06-30 会话增量归档：简报交付与模拟账户运维

## 范围

- 本轮主要处理项目外静态站点交付、每日简报远端同步、新模拟账户重启、模拟账户账单页面和账户执行口径说明。
- 未进行策略规则、准入规则、回测算法或核心数据模型重构。

## 新增标准与关键决策

- `share.spidermanread.men` 作为 Vultr VPS 上新的静态交付域名。
- 简报公网路径固定为 `http://share.spidermanread.men/brief/`，远端目录为 `/var/www/spidermanread/brief/`。
- 模拟账户账单公网路径固定为 `http://share.spidermanread.men/account-bill/`，远端目录为 `/var/www/spidermanread/account-bill/`。
- 本轮早先按用户要求不修改 `.env`；后续代码改造中保留环境变量覆盖能力：
  - `BRIEF_SYNC_REMOTE` / `BRIEF_SYNC_REMOTE_DIR` 仍控制 watchlist/brief 同步。
  - 新增 `ACCOUNT_BILL_SYNC_REMOTE` / `ACCOUNT_BILL_SYNC_REMOTE_DIR` 控制账单同步。
- 模拟账户已按“新账户重启”口径处理：以 `2026-06-30` 为新账户首日建仓观察日，旧模拟状态先归档，再用零仓位占位 ledger 让当日观察池从 `0.00%` 当前暴露开始。
- 观察池是计划层，展示目标权重；模拟账户账单是执行层，只有执行日 OHLCV 入库后才会生成确认成交、持仓和盈亏。
- 模拟账户执行层已按 `lot_size=100` 做 A 股整手约束，并同时考虑现金、最大成交参与率、涨跌停和停牌检查；观察池目标权重本身不先换算为整手。

## 服务器与远端站点操作

- 由子智能体 Luke 在 Vultr VPS `linuxuser@108.61.182.91` 配置 Nginx 站点：
  - Nginx 配置文件：`/etc/nginx/conf.d/share.spidermanread.men.conf`
  - Web 根目录：`/var/www/spidermanread/`
  - 简报目录：`/var/www/spidermanread/brief/`
  - 已执行 `nginx -t` 和 `systemctl reload nginx`
  - 当前仅配置 HTTP，未配置 HTTPS。
- 主线程创建账单目录和占位页：
  - `/var/www/spidermanread/account-bill/index.html`
  - 公网校验 `http://share.spidermanread.men/account-bill/` 返回 `200`。

## 本地执行命令摘要

- 生成并同步今日简报：
  - `BRIEF_SYNC_REMOTE=linuxuser@108.61.182.91 BRIEF_SYNC_REMOTE_DIR=/var/www/spidermanread/brief/ ./.venv/bin/python -m phase0.cli brief watchlist --config config.yaml --refresh-cache`
  - 结果：信号日 `2026-06-29`，盘前检查时间 `2026-06-30 07:30`。
- 新模拟账户重启：
  - 备份目录：`data/simulated_trading/archive/sim_account_legacy_until_2026-06-29__20260630_090436/`
  - 写入 `2026-06-29` 零仓位占位 ledger。
  - 重新生成并同步新账户首日建仓版简报。
- 新账户首日建仓版校验：
  - 当前总暴露：`0.00%`
  - 目标总暴露：`10.20%`
  - 买入/加仓：`5`
  - 卖出/减仓：`0`
- 账单页面集成验证：
  - `BRIEF_SYNC_REMOTE=linuxuser@108.61.182.91 BRIEF_SYNC_REMOTE_DIR=/var/www/spidermanread/brief/ ACCOUNT_BILL_SYNC_REMOTE=linuxuser@108.61.182.91 ACCOUNT_BILL_SYNC_REMOTE_DIR=/var/www/spidermanread/account-bill/ ./.venv/bin/python -m phase0.cli brief watchlist --config config.yaml --skip-update`
  - 结果：watchlist 同步正常；因当前无确认账单 HTML，account-bill 同步安全跳过。

## 代码变更

- 修改 `phase0/cli_commands/delivery.py`：
  - 新增 `ACCOUNT_BILL_TODAY_DIR = "reports/account_bill_today"`。
  - 新增 `_copy_account_bill_latest(...)`，将真实账单 HTML 镜像到：
    - `reports/runs/latest/account_bill/index.html`
    - `reports/account_bill_today/index.html`
  - 新增 `_sync_account_bill_to_cloud(...)`，默认同步到 `linuxuser@108.61.182.91:/var/www/spidermanread/account-bill/`。
  - `brief watchlist` 在存在真实账单 HTML 时自动同步账单；无账单时不报错、不覆盖远端占位页。
  - `brief account-bill` 手动导出后也会更新 latest 镜像并同步远端。
- 修改 `tests/test_cli_delivery_commands.py`：
  - 覆盖 watchlist 生成账单时的 latest 镜像与云同步。
  - 覆盖账单缺失时跳过同步的边界。
  - 覆盖手动 `brief account-bill` 导出后的账单镜像与同步。

## 生成或更新的本地产物

- `reports/watchlist_today/index.html`
- `reports/runs/latest/watchlist/index.html`
- `data/simulated_trading/phase0_daily_brief_ledger.csv`
- `data/simulated_trading/archive/sim_account_legacy_until_2026-06-29__20260630_090436/`

## 验证结果

- `./.venv/bin/python -m pytest tests/test_cli_delivery_commands.py -q`
  - 结果：`6 passed`
- 公网校验：
  - `http://share.spidermanread.men/brief/` 返回新账户首日建仓版简报。
  - `http://share.spidermanread.men/account-bill/` 返回账单占位页。

## 当前限制与风险

- 当前未配置 HTTPS；公网访问为 HTTP。
- `2026-06-30` 新账户首日的执行日 OHLCV 尚未入库，因此 `account_daily_assets`、`account_trades`、`account_positions` 当前仍为空。
- 模拟账户账单只有在执行日行情入库后才会产生确认成交、持仓快照和盈亏；当前 `/brief/` 只代表计划层建仓建议。
- 账户执行层虽然已有整手、现金、涨跌停、停牌和最大成交参与率约束，但未成交/部分成交原因在账单展示上的结构化可读性仍需增强。
- 当前 `ACCOUNT_BILL_SYNC_REMOTE` 默认写入代码，后续如果远端服务器再变更，应优先通过环境变量覆盖。

## 下一步建议

- 待 `2026-06-30` 行情入库后，重跑 `brief watchlist`，检查是否生成首日确认成交账单，并确认 `/account-bill/` 自动更新。
- 增强 account-bill 页面，补充累计收益曲线、历史交易列表、当前持仓汇总和未成交原因。
- 将 `share.spidermanread.men` 接入 HTTPS。
- 若用户希望长期保持项目外远端默认地址，后续需明确是否把 `BRIEF_SYNC_REMOTE` 默认值也从旧 ECS 迁移到 Vultr，或只在调度器外部环境中配置。
