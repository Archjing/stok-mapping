# Session Incremental Archive - 2026-06-25 14:25

## 新增用户标准

- 每做完一轮 Harness，进行一次 Git 提交。
- 提交和推送要谨慎控制范围：重点上传项目代码、测试、解释代码的文档、轻量配置和轻量简报；大型生产产物、原始 evidence CSV、运行日志和数据维护产物默认只本地落盘，不上传远端。

## 本轮目标

延续 I46 后的强沪深300归因研发，执行 I47：把强市场参与策略拆成“稳定核心底仓 + alpha 卫星”，验证是否能降低换手、提高沪深300核心覆盖，并保持 research-only 和 admission gate 不变。

## Harness 分工

- Team Lead：控制范围、实现核心代码、运行验证、生成简报、准备提交。
- Planner：只读审查 I47 方案，建议不要继续微调 I46，而是把核心底仓和 alpha 卫星分层；强调趋势、流动性、风险、行业约束只能做软约束。
- Implementer 辅助：第一位 agent 因上游 502 失败；替代 agent 建议新增独立策略类，不覆盖 I46。
- Reviewer：列出 PIT、qfq_asof、成本、行业审计、research-only 边界和报告一致性检查点。
- Verifier：指出 I47 最应改善的指标是参与仓位、沪深300权重覆盖、Top20 覆盖、行业偏离，同时换手仍是 admission 硬门槛。

## 主要代码变更

- 新增 `phase0/strategies/strong_market_stable_core_base.py`
  - 策略名：`strong_market_stable_core_base_v1`
  - research-only：`supports_brief=False`，`supports_paper_trade=False`
  - 设计：非强市场不再全空仓，而是保留 `base_exposure=0.35` 的稳定核心底仓；强市场提高到 `strong_target_exposure=0.70`，其中核心预算约 `0.82`，卫星预算约 `0.18`。
  - 核心股只做基础可交易性硬过滤；趋势、流动性、风险、行业变量只参与排序、降权和审计，不硬剔除沪深300核心股。
  - 默认 `rebalance_days=20`，避免 I46 高换手问题。
- 更新 `phase0/strategies/__init__.py` 注册新策略。
- 更新 `phase0/strategy_admission.py`，让 scoped strategy set 能强制启用 `local_factor.strong_market_stable_core_base`。
- 新增 `tests/test_strong_market_stable_core_base_strategy.py`。
- 更新 `tests/test_strategy_admission_config.py`。
- 新增 `config.main_strategy_i47_strong_market_stable_core_base_20260625.yaml`，只作为本地研究配置，不改 `config.yaml`。

## 运行命令

```bash
./.venv/bin/python -m pytest -s tests/test_strong_market_stable_core_base_strategy.py tests/test_strong_market_core_participation_strategy.py tests/test_strategy_admission_config.py

./.venv/bin/python -m py_compile phase0/strategies/strong_market_stable_core_base.py phase0/strategies/__init__.py phase0/strategy_admission.py

./.venv/bin/python -m phase0.cli strategy-admission --config config.main_strategy_i47_strong_market_stable_core_base_20260625.yaml --presets baseline_2y_1y_5fold --strategy-set i47_strong_market_stable_core_base_v1 --output-dir reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_47__strong_market_stable_core_base/admission

./.venv/bin/python -m phase0.cli strategy-failure-attribution --config config.main_strategy_i47_strong_market_stable_core_base_20260625.yaml --admission-dir reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_47__strong_market_stable_core_base/admission --output-dir reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_47__strong_market_stable_core_base/failure_attribution

./.venv/bin/python -m phase0.cli strategy-market-context --config config.main_strategy_i47_strong_market_stable_core_base_20260625.yaml --fold-attribution reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_47__strong_market_stable_core_base/failure_attribution/strategy_failure_fold_attribution.csv --output-dir reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_47__strong_market_stable_core_base/market_context

./.venv/bin/python -m phase0.cli strategy-holdings-exposure --config config.main_strategy_i47_strong_market_stable_core_base_20260625.yaml --candidate-folds reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_47__strong_market_stable_core_base/admission/strategy_admission_candidate_folds.csv --market-context reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_47__strong_market_stable_core_base/market_context/strategy_market_context_diagnostic.csv --strategy strong_market_stable_core_base_v1 --output-dir reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_47__strong_market_stable_core_base/holdings_exposure

./.venv/bin/python -m phase0.cli strategy-csi300-attribution --config config.main_strategy_i47_strong_market_stable_core_base_20260625.yaml --holdings reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_47__strong_market_stable_core_base/holdings_exposure/strategy_daily_holdings.csv --daily-exposure reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_47__strong_market_stable_core_base/holdings_exposure/strategy_daily_exposure.csv --candidate-folds reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_47__strong_market_stable_core_base/admission/strategy_admission_candidate_folds.csv --market-context reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_47__strong_market_stable_core_base/market_context/strategy_market_context_diagnostic.csv --context-label all --output-dir reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_47__strong_market_stable_core_base/csi300_attribution_all_context
```

## 验证结果

- 单测：`41 passed, 1 warning`
- 编译检查：通过
- I47 admission：`reject`
- 年化收益均值：`-1.74%`
- Sharpe：`-0.34`
- 正收益折比例：`40%`
- 正超额折比例：`40%`
- 年化换手均值：`0.68`
- 年化换手最大值：`1.85`
- overfit risk：`high`
- 行业集中窗口：`1`
- PIT 权重日期审计：`bad_same_or_future_weight_rows = 0`

## I46 / I47 对比

| 指标 | I46 | I47 |
| ---- | ----: | ----: |
| 年化收益均值 | `-3.30%` | `-1.74%` |
| Sharpe | `-0.43` | `-0.34` |
| 正收益折比例 | `0%` | `40%` |
| 正超额折比例 | `60%` | `40%` |
| 年化换手均值 | `4.08` | `0.68` |
| 年化换手最大值 | `16.04` | `1.85` |
| 平均实盘暴露 | `3.93%` | `36.58%` |
| 策略权重中落在沪深300内的比例 | `3.15%` | `35.98%` |
| Top20 覆盖率 | `3.66%` | `58.16%` |
| 行业偏离 | `0.89` | `1.15` |

## 结论

I47 仍不是可用策略，不能进入 paper review、模拟账户、日报或 watchlist。它的价值是把强沪深300参与线推进到新的失败边界：稳定核心底仓能明显提高参与度、沪深300核心覆盖和换手质量，但收益质量、强市低配、行业偏离和 overfit 仍未解决。

## 本轮报告

- `reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/briefings/iter_47__strong_market_stable_core_base_brief.md`
- 原始 evidence 目录本地保留：`reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_47__strong_market_stable_core_base/`

## 下一步

I48 不做参数搜索，先做核心-only / 核心+卫星 / 卫星-only 拆分归因，验证 I47 的 alpha 卫星到底贡献收益，还是增加行业偏离和噪声。
