# T6.7｜多模拟账户静态控制台方案

> 最后修订：2026-06-30  
> 状态：第一阶段已实施。后续重点是补逐笔未成交事件表和正式 daily brief 页面。

## 目标

在现有 `share.spidermanread.men` 站点下新增隔离入口 `/quant/`，用于查看多个模拟账户的盘前观察池、模拟交易账单和完整交易台账。该控制台只发布静态 HTML/CSS/JSON/CSV，不上传 SQLite，不覆盖站点根目录，不影响旧 `/brief/` 与 `/account-bill/` 页面。

## 设计边界

- 远端根目录 `/var/www/spidermanread` 是已有站点根目录，禁止整目录覆盖或对根目录执行 `rsync --delete`。
- 新控制台只同步到 `/var/www/spidermanread/quant/`。
- 多账户来源统一读取 `config.yaml` 的 `accounts.simulated`；只有 `enabled: true` 的账户参与生成。
- 每个账户可以配置自己的 `strategy_id`、`simulation_start_date`、初始资金、执行价口径和最大成交参与率。
- 模拟账户 SQLite 继续使用共享账本表，通过 `account_id` 区分账户；当前不拆成每账户一个物理数据库或每账户一组三张表。
- 观察池和账单 latest 必须从账户级产物读取，不能把默认账户页面复制给所有账户。

## 已实施内容

- 新增静态控制台生成模块：`phase0/reporting/quant_static_site.py`。
- 新增 CLI 入口：
  - `runit site build --config config.yaml`
  - `runit site sync --config config.yaml`
  - `runit site publish --config config.yaml`
- 新增本地发布目录：
  - `reports/static_site/quant/`
- 新增远端安全同步默认值：
  - `QUANT_SITE_SYNC_REMOTE=linuxuser@108.61.182.91`
  - `QUANT_SITE_SYNC_REMOTE_DIR=/var/www/spidermanread/quant/`
- `sync` 会校验远端目录必须以 `/quant/` 结尾，避免误同步到 `/var/www/spidermanread/` 根目录。
- `brief watchlist --all-accounts` 已按所有 enabled 账户生成账户级 latest watchlist 和 account-bill 产物，供 `/quant/` 控制台采集。

## 站点结构

```text
reports/static_site/quant/
├── index.html
├── assets/
│   └── watchlist.css
├── data/
│   └── site_manifest.json
└── accounts/
    └── <account_id>/
        ├── index.html
        ├── latest/
        │   ├── watchlist/
        │   │   └── index.html
        │   └── account-bill/
        │       └── index.html
        ├── ledger/
        │   └── index.html
        └── dates/
            └── <YYYY-MM-DD>/
                ├── daily-assets.csv
                ├── trades.csv
                └── positions.csv
```

## 数据来源

| 页面 | 数据来源 | 说明 |
| --- | --- | --- |
| `/quant/index.html` | `accounts.simulated` + `account_daily_assets` | 账户总览、最新账单日、总资产、仓位 |
| `/quant/accounts/<account_id>/latest/watchlist/` | `reports/runs/latest/accounts/<account_id>/watchlist/` | 账户自己的盘前观察池 |
| `/quant/accounts/<account_id>/latest/account-bill/` | `reports/runs/latest/accounts/<account_id>/account_bill/` | 账户自己的最新模拟账单 |
| `/quant/accounts/<account_id>/ledger/` | `account_daily_assets`、`account_trades`、`account_positions` | 完整交易台账 |
| `/quant/data/site_manifest.json` | 生成时汇总 | 供后续 dashboard 或脚本读取 |

## 推荐日常流程

```bash
# 1. 为所有启用账户生成最新观察池和模拟账单
./runit brief watchlist --config config.yaml --all-accounts

# 2. 本地构建多账户静态控制台
./runit site build --config config.yaml

# 3. 发布到远端 /quant/，不触碰站点根目录
./runit site publish --config config.yaml
```

如果只想检查本地页面，不执行远端同步，只跑 `site build`。

## 验收标准

- `reports/static_site/quant/index.html` 存在。
- `reports/static_site/quant/data/site_manifest.json` 包含所有 enabled 模拟账户。
- 每个账户都有独立的：
  - `accounts/<account_id>/latest/watchlist/index.html`
  - `accounts/<account_id>/latest/account-bill/index.html`
  - `accounts/<account_id>/ledger/index.html`
- `site sync` 只调用远端 `/var/www/spidermanread/quant/`。
- SQLite 数据库不进入静态站点，也不上传远端。
- 旧 `/brief/` 与 `/account-bill/` 仍可继续访问。

## 后续任务

- [ ] 新增 `account_order_events` 表，记录未成交、部分成交、整手归零、现金不足、涨跌停、停牌、T+1 等逐笔原因。
- [ ] 将正式 `daily brief` 从当前 watchlist 兼容实现中拆出后，接入 `/quant/` 的账户页。
- [ ] 为多账户控制台增加更清晰的账户策略说明、建仓日、执行 profile 和数据新鲜度状态。
- [ ] 后续若有多个模拟账户长期运行，增加按账户过滤的回放页和月度复盘页。
