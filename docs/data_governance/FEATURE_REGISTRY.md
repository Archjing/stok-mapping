# 技术指标注册与构建层（Feature Registry）

> 状态：Tier-A 本地价格/量能技术指标已实现，registry 元数据层已可用。  
> 对应归档计划：`docs/archive/superpowers/plans/2026-08-03-data-capability-gap-closure-program.md` Phase 1。

## 定位

这是"后续策略因子开发的基础设施"：一个**只读、无 I/O、无网络、不落盘**的元数据注册表 + 纯函数构建器集合。消费者对某个 `symbol × date` 面板请求一组命名特征，registry 解析依赖顺序并从本地已有字段计算出来。

它**不**预计算特征湖、**不**下载数据、**不**改变现有 `qfq_asof` 复权选择（那是 `local_history` / walk-forward 层的职责）。

## 核心契约（FeatureSpec）

| 字段 | 说明 |
| --- | --- |
| `name` | 稳定输出列名，如 `ema_20`、`rsi_14`、`drawdown_60` |
| `version` | 语义化公式版本；公式变更必须升版本或显式迁移 |
| `inputs` | 依赖的源列/特征名 |
| `lookback_sessions` | 所需最大回看窗口（含 warm-up） |
| `availability_lag_sessions` | `0` 表示仅盘后可用同日收盘；下一交易日执行排名须应用现有执行延迟 |
| `missing_data_policy` | `preserve_nan` \| `drop_until_warm`；禁止 backward fill |
| `builder` | 纯函数：排序后的面板 → 对齐原索引的 Series/DataFrame |

## 分层（Feature tiers）

- **Tier A — 本地价格/量能**（已实现）：return、gap、range、MA/EMA/MACD/RSI/Bollinger、momentum/reversal、volume change/shock、rolling high/low、drawdown、turnover。
- **Tier B — 受治理的本地 join**（未实现）：复权、财务 PIT、指数与行业特征；需 as-of 审计字段与覆盖率指标。
- **Tier C — 外部 opt-in**（未实现）：宏观、外汇、商品、研报预期与文本；需来源契约，registry import 不能隐式启用。

## 已实现特征（Tier A，28 个）

`return_1`、`open_close_return_1`、`gap_return_1`、`range_pct_1`、`volume_change_1`、`amount_change_1`、`volatility_20`、`rolling_high_20`、`rolling_low_20`、`drawdown_60`、`ma_3/5/10/20/60`、`ema_12/26`、`macd_line_12_26`、`macd_signal_9`、`macd_hist_12_26_9`、`rsi_14`、`bollinger_mid_20`、`bollinger_upper_20_2`、`bollinger_lower_20_2`、`momentum_5/20`、`reversal_5`、`amount_ratio_20`、`volume_shock_z20`、`turnover_rate`。

## 使用示例

```python
from quant.research.features import build_technical_registry

registry = build_technical_registry()
panel = ...  # 含 symbol/date/open/high/low/close/volume/amount/turnover_rate
result = registry.build(panel, ("rsi_14", "ma_20", "momentum_20"))
```

## 公式约定

- 所有 rolling/EMA 按 `symbol` 分组，`sort_values(["symbol", "date"], kind="stable")` 后计算，杜绝跨标的串数据。
- `bollinger_*` 标准差 `ddof=0`。
- `reversal_5 = -momentum_5`。
- `volume_shock_z20 = (log(volume) - rolling_mean(log(volume),20)) / rolling_std(log(volume),20)`，窗口不全或分母为零返回 NaN。
- `rsi_14`：`avg_loss == 0` 且 `avg_gain > 0` 时 RSI = 100；两者皆 0 时 NaN。

## 与 legacy walk-forward 的等价性

`tests/test_technical_equivalence.py` 锁定重叠列（`ma20`/`mom20`/`vol20`/`oc_ret`）与 `quant/walk_forward.py` 一致。已知语义差异：legacy `vol20` 用 `pct_change().fillna(0)` 使窗口提前一个 session 出值，registry 保留 NaN（`preserve_nan`）；迁移时须在 decision record 中解释，不能静默改变策略信号。

## 边界

- 新特征默认 `materialize_by_default=False`、`allow_network=False`、`frequency=daily`。
- Tier B/C 在 Phase 2 价格治理 gate 通过前不得进入策略实验/admission。
