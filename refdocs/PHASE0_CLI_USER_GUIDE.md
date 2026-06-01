# Phase0 CLI 使用说明（当前版本）

适用范围：`python -m phase0.cli` 当前已实现命令。  
默认配置文件：`config.yaml`。  
说明口径：以 [phase0/cli.py](/home/zj/workspace/stok-mapping/phase0/cli.py) 实际参数为准。

---

## 1. 快速开始

安装依赖（项目根目录）：

```bash
uv sync
```

查看总帮助：

```bash
./.venv/bin/python -m phase0.cli -h
```

最常用的三个命令：

```bash
# 全量 Phase0 主流程
./.venv/bin/python -m phase0.cli run --config config.yaml

# 仅更新 A 股本地历史库
./.venv/bin/python -m phase0.cli update-history --config config.yaml

# 导出 07:30 盘前观察池
./.venv/bin/python -m phase0.cli premarket --config config.yaml
```

---

## 2. 命令总览

`phase0.cli` 当前支持以下子命令：

- `run`
- `cost-sensitivity`
- `bill`
- `market-regime`
- `oos-report`
- `financial-pti`
- `premarket`
- `execution-gate`
- `build-universe`
- `import-history`
- `import-index-history`
- `update-history`
- `update-us-market-history`
- `update-hk-market-history`
- `update-financials`

---

## 3. 命令详解

### 3.1 主流程与策略评估

`run`：执行 Phase0 主流程（数据源连通性、质量审计、walk-forward、effectiveness report、账单导出）。

```bash
./.venv/bin/python -m phase0.cli run --config config.yaml
```

`cost-sensitivity`：成本敏感性单独运行，不与 `run` 自动绑定。

```bash
# 手动传场景
./.venv/bin/python -m phase0.cli cost-sensitivity --config config.yaml \
  --scenario base:0.001 --scenario stress:0.003

# 使用 config.yaml 的 cost_sensitivity.scenarios
./.venv/bin/python -m phase0.cli cost-sensitivity --config config.yaml --use-config-scenarios
```

### 3.2 导出类命令

`bill`：导出低换手账单与资产曲线文件。

```bash
./.venv/bin/python -m phase0.cli bill --config config.yaml
./.venv/bin/python -m phase0.cli bill --config config.yaml --refresh-cache
./.venv/bin/python -m phase0.cli bill --config config.yaml --no-panel-cache
```

`oos-report`：导出连续 OOS 报告，支持执行参数 profile 和临时覆盖。

```bash
./.venv/bin/python -m phase0.cli oos-report --config config.yaml --profile research
./.venv/bin/python -m phase0.cli oos-report --config config.yaml --profile live \
  --slippage 0.003 --price-mode conservative --max-participation-rate 0.03
```

`execution-gate`：账户级执行有效性门控报告。

```bash
./.venv/bin/python -m phase0.cli execution-gate --config config.yaml --profile live
./.venv/bin/python -m phase0.cli execution-gate --config config.yaml --profile research \
  --output-dir reports/live_execution_backtest/research_profile
```

`premarket`：导出 07:30 盘前观察池。

```bash
./.venv/bin/python -m phase0.cli premarket --config config.yaml
```

`market-regime`：导出行情分段验证报告。

```bash
./.venv/bin/python -m phase0.cli market-regime --config config.yaml
```

`financial-pti`：财务因子 point-in-time 校验。

```bash
./.venv/bin/python -m phase0.cli financial-pti --config config.yaml
```

### 3.3 数据库导入与更新

`import-history`：从本地压缩包重建 A 股历史库（首次建库或重建）。

```bash
./.venv/bin/python -m phase0.cli import-history --config config.yaml
```

`import-index-history`：仅重建指数元数据和指数日线表。

```bash
./.venv/bin/python -m phase0.cli import-index-history --config config.yaml
```

`update-history`：A 股历史库增量更新。

```bash
# 实际更新
./.venv/bin/python -m phase0.cli update-history --config config.yaml

# 只检查新鲜度，不写库
./.venv/bin/python -m phase0.cli update-history --config config.yaml --check-only

# 更新后不自动重建 universe
./.venv/bin/python -m phase0.cli update-history --config config.yaml --no-build-universe
```

`update-us-market-history`：US market 本地库增量更新。

```bash
./.venv/bin/python -m phase0.cli update-us-market-history --config config.yaml
./.venv/bin/python -m phase0.cli update-us-market-history --config config.yaml --check-only
```

`update-hk-market-history`：港股本地库增量更新。

```bash
./.venv/bin/python -m phase0.cli update-hk-market-history --config config.yaml
./.venv/bin/python -m phase0.cli update-hk-market-history --config config.yaml --check-only
```

`update-financials`：更新 A 股季度财务因子。

```bash
./.venv/bin/python -m phase0.cli update-financials --config config.yaml
./.venv/bin/python -m phase0.cli update-financials --config config.yaml --periods 16
./.venv/bin/python -m phase0.cli update-financials --config config.yaml --no-build-universe
```

`build-universe`：单独构建本地因子股票池。

```bash
./.venv/bin/python -m phase0.cli build-universe --config config.yaml
```

---

## 4. 关键输出文件

常见输出路径：

- `reports/phase0_data_source_report.md`
- `reports/phase0_walk_forward_report.md`
- `reports/phase0_effectiveness_report.md`
- `reports/phase0_walk_forward_folds.csv`
- `reports/phase0_walk_forward_candidates.csv`
- `reports/phase0_cost_sensitivity_report.md`
- `reports/phase0_cost_sensitivity.csv`
- `reports/phase0_low_turnover_bill.csv`
- `reports/phase0_low_turnover_bill_preview.html`
- `reports/phase0_premarket_watchlist.csv`
- `reports/phase0_premarket_watchlist_report.html`

本地数据库：

- `data/manual_history/a_share_history.sqlite`
- `data/us_market_history.sqlite`
- `data/hk_market_history.sqlite`

---

## 5. 当前配置要点（与你现在的状态相关）

- A 股主链路：`Tushare + 本地 SQLite`
- US market：当前仍为 `yfinance` 过渡 provider（Tiingo 已最小接入）
- 港股：当前配置已切到 `tushare_hk` provider，并启用 `hk_market_history`
- 港股落库表：`hk_daily_bars`，含 `hk` 字段（港股行写 `HK`）

---

## 6. 常见问题与排查

### 6.1 `status=stale` 且 `rows=0`

常见原因：

- 数据源接口限频
- token 无权限
- 网络/DNS 不可达
- symbol 列表为空或格式不合法

排查顺序：

1. 先跑 `--check-only` 看覆盖率和最新日期。  
2. 再看 `Warning` 里的原始报错。  
3. 单独跑对应 provider 的最小抓取脚本（单标的、短区间）。  
4. 必要时切换 provider 或缩小 symbols。

### 6.2 OOS/Execution 参数覆盖

`oos-report` 与 `execution-gate` 支持临时参数覆盖：

- `--slippage`
- `--commission`
- `--stamp-duty-sell`
- `--price-mode`
- `--lot-size`
- `--max-participation-rate`
- `--enable-limit-check / --no-enable-limit-check`
- `--enable-suspension-check / --no-enable-suspension-check`

建议优先用 `--profile research|live`，只在压力测试时覆盖单项参数。

---

## 7. 推荐工作流

日常（开发/研究）：

1. `update-history`
2. `update-financials`（按周）
3. `update-us-market-history`
4. `update-hk-market-history`
5. `run`
6. `premarket`

验收（策略阶段）：

1. `run`
2. `execution-gate --profile live`
3. `oos-report --profile live`
4. `cost-sensitivity --use-config-scenarios`
5. `market-regime`
6. `financial-pti`

---

## 8. 参考源码

- CLI 入口：[phase0/cli.py](/home/zj/workspace/stok-mapping/phase0/cli.py)
- 数据源适配：[phase0/data_sources.py](/home/zj/workspace/stok-mapping/phase0/data_sources.py)
- US/HK 历史库更新：[phase0/external_market_history.py](/home/zj/workspace/stok-mapping/phase0/external_market_history.py)
- A 股增量更新：[phase0/update_history.py](/home/zj/workspace/stok-mapping/phase0/update_history.py)
