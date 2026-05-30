# Phase 0 Strategy Change Log

Generated at: 2026-05-29T02:49:58

## 2026-05-29: xmarket_magnitude_soft_risk_v1

Change:
- Added a comparison-only candidate named `xmarket_magnitude_soft_risk_v1`.
- Kept `legacy_momentum`, `xmarket_single_v2`, `xmarket_portfolio_v2`, and `xmarket_next_open_v1` unchanged as comparable candidates.
- Added `phase0_walk_forward_candidates.csv` to save all candidate folds, while `phase0_walk_forward_folds.csv` still saves the selected candidate folds.

Strategy logic:
- Cross-market return magnitude is standardized with rolling z-scores before aggregation.
- The aggregation keeps the previous directional weights: positive `^NDX`, `^SOX`, `NVDA`, `KWEB`; negative `^VIX`, `CNY=X`.
- A single risk event no longer forces a hard exclusion in this candidate. It applies `risk_scale` to position size instead.
- The candidate still requires A-share momentum/trend/volatility confirmation.

Parameters:
- `magnitude_z_window: 252`
- `magnitude_z_min_periods: 60`
- `magnitude_z_clip: 2.0`
- `magnitude_score_thresholds: [0.0]`
- `soft_risk_scale: 0.5`

Reason and reference:
- Previous Phase 0 diagnostics showed the hard `risk_off` filter covered about 29% of days, so a hard all-or-nothing exclusion was likely too blunt for an early Phase 0 rule.
- Previous candidate results showed `xmarket_next_open_v1` underperformed, so the next test should not keep tuning entry timing alone.
- Cross-asset returns have materially different volatility profiles, so raw magnitude thresholds are not directly comparable across `^NDX`, `^SOX`, `NVDA`, `KWEB`, `^VIX`, and `CNY=X`. Rolling z-score normalization tests whether relative surprise magnitude adds value beyond direction.
- `252` was chosen as an approximate one-year trading window to avoid a short-window overfit in Phase 0.
- `60` minimum observations allow the factor to initialize after roughly one quarter while still requiring enough history for a stable estimate.
- `2.0` clipping limits extreme z-score outliers from dominating a small Phase 0 sample.
- `0.0` threshold keeps the first magnitude candidate simple: it tests positive standardized cross-market pressure rather than searching many thresholds.
- `0.5` soft risk scale tests whether stress days should reduce exposure instead of fully eliminating positions.

Latest result:
- Selected candidate remains `legacy_momentum`.
- `xmarket_magnitude_soft_risk_v1`: annualized return mean `-0.1078`, Sharpe mean `-1.1988`, max drawdown mean `-0.1983`.
- Conclusion: do not promote this candidate to the main strategy. Keep it only as a failed comparison baseline unless later evidence changes.

## 2026-05-29: residual_momentum_reversal_v1

Change:
- Added a comparison-only candidate named `residual_momentum_reversal_v1`.
- Updated the project plan so the main strategy path is now A-share local factors first, with cross-market signals used as a risk/sentiment overlay.
- Kept all previous candidates in the comparison set.

Strategy logic:
- Residual momentum is approximated as individual stock momentum minus same-date symbol-pool average momentum.
- A 3-day reversal filter removes short-term overheated names.
- Trend confirmation still requires price above a moving average.
- Volatility filter remains based on `vol20` quantiles.
- Cross-market signal is not used for ranking; it only applies `risk_scale` when `use_xmarket_overlay` is enabled.

Parameters:
- `residual_momentum_windows: [10, 20]`
- `residual_momentum_quantiles: [0.6]`
- `reversal_window: 3`
- `reversal_quantiles: [0.7]`
- `use_xmarket_overlay: true`

Reason and reference:
- Phase 0 results showed direct cross-market ranking underperformed `legacy_momentum`, so cross-market factors should not remain the main ranker.
- Recent A-share literature supports testing short-horizon momentum/reversal and residual-style momentum more than plain medium-horizon momentum.
- `10` and `20` trading-day windows were chosen as short-to-one-month horizons, avoiding overly noisy 3/5-day primary signals while staying closer to the A-share short-horizon evidence than classic 6-12 month momentum.
- `3` trading days for reversal targets very short-term overheating; it is a filter, not the primary alpha.
- `0.6` residual momentum threshold is intentionally sparse but not extreme for a small Phase 0 sample.
- `0.7` reversal threshold excludes the most overheated 30% on the short reversal leg.
- Current data lacks industry, market-cap, and fundamental fields, so this is only a pool-relative residual approximation. It must not be treated as a full industry/size-neutral residual factor.

Latest result:
- Selected candidate remains `legacy_momentum`.
- `residual_momentum_reversal_v1`: annualized return mean `-0.0539`, Sharpe mean `-0.3902`, max drawdown mean `-0.1477`.
- It improves drawdown versus `legacy_momentum` but loses money and has negative Sharpe in the current Phase 0 setup.
- Conclusion: do not promote this candidate to the main strategy. Next useful step is to add industry, market-cap, liquidity, and fundamental data before retesting local factor candidates.

## 2026-05-29: project progress checkpoint

Status summary:
- Phase 0 infrastructure is largely in place: local A-share history database, index history, trading calendar, delisted stock list, walk-forward framework, universe builder, and candidate comparison outputs are all available.
- Quarterly financial factors are now integrated into the local database and documented in `README.md`, including `roe`, `revenue_growth`, `profit_growth`, `operating_cash_flow_to_net_profit`, and `debt_to_asset`.
- Research-document support is now substantially improved: English/open-access reference papers, Chinese A-share papers, strategy summaries, development checklists, candidate strategy notes, local LLM recommendations, and local LLM implementation plans have all been archived under `refdocs/`.

Current strategy state:
- Current selected candidate remains `legacy_momentum`.
- The latest effectiveness gate still fails overall.
- Snapshot from `reports/phase0_effectiveness_report.md`:
  - `annualized_return_mean`: `0.33599064897406206` (pass)
  - `sharpe_mean`: `0.3357946743577156` (fail vs `> 0.5`)
  - `max_drawdown_mean`: `-0.30737744830217145` (fail vs `> -0.25`)
  - `win_rate_mean`: `0.46218977423976626` (pass)
  - `oos_return_decay_ratio`: `-1.8724556472813825` (pass)
- Interpretation: return level is acceptable for Phase 0, but the risk-adjusted profile and drawdown are not yet good enough to pass the gate.

What is effectively done:
- Data foundation: usable.
- Walk-forward framework: usable.
- Candidate comparison framework: usable.
- Financial factor ingestion: available but not yet fully promoted into the main ranking logic.
- Documentation and literature review layer: strong enough to guide the next strategy iteration.
- Local LLM selection and implementation planning: documented, but not the main bottleneck.

Main blocker:
- The project is no longer blocked by data plumbing or documentation. The main blocker is still alpha quality: the main strategy has not yet passed the effectiveness gate.

Recommended next focus:
- Prioritize strategy iteration over agent automation.
- The next practical candidates to test remain:
  1. short-horizon residual momentum + reversal enhancement,
  2. multi-factor + volume/price second-stage filtering,
  3. simple MA/K-line baseline.
- Primary objective for the next cycle is not higher raw return first, but improving `sharpe_mean` above `0.5` and reducing `max_drawdown_mean` to better than `-0.25`.
- The current effectiveness gate should be interpreted as a three-layer filter rather than a pure return maximization rule: (1) first require positive annualized return, (2) then require acceptable stability and risk (`sharpe`, `drawdown`, `win_rate`), and (3) finally require acceptable out-of-sample decay. This means the project is looking for strategies that not only make money, but can also be held through volatility and still survive on new data.

## 2026-05-29: Tiingo / FRED data-source feasibility review

Change:
- Evaluated whether the current US-market research source setup should move away from `yfinance`.
- Reviewed a layered replacement path instead of a one-shot replacement.
- Defined a recommended role split among Tiingo, FRED, yfinance, and the existing A-share stack.

Findings:
- Replacing all current US-side `yfinance` usage with Tiingo in one step is technically possible, but not the best immediate move.
- Tiingo is a better fit than `yfinance` for **formal US equities / ETF end-of-day ingestion**, especially for symbols such as `NVDA`, `AAPL`, `TSLA`, and `KWEB`.
- FRED is a better fit than both Tiingo and `yfinance` for **macro series and rates**, including GDP, CPI, federal funds, and a daily VIX proxy series.
- `yfinance` should not remain the long-term primary US data source, but it still has value as a low-friction development / research fallback.
- CNH / FX proxy data should not be rushed into the same replacement wave; it can remain on `yfinance` temporarily until there is a clearer production-grade FX plan.

Recommended layered target state:
- A-share daily / cross-sectional core: `Tushare Pro` primary, local SQLite fallback, AkShare/Sina as secondary fallback.
- US equities / thematic ETFs EOD: `Tiingo` primary, `yfinance` fallback.
- Macro / rates / VIX family: `FRED` primary.
- FX proxy (`CNY=X`-style overlay input): keep temporary `yfinance` fallback until separately upgraded.

Reason and reference:
- The project now distinguishes between **formal batch data sources** and **research fallback sources**.
- Current project architecture benefits more from source specialization than from forcing one vendor to cover all US-side use cases.
- Tiingo provides a cleaner path for EOD US equity / ETF ingestion and future intraday expansion.
- FRED is structurally more appropriate for low-frequency macro and policy-sensitive overlay inputs than `yfinance`.

Adjustment suggestion:
1. Introduce `fred` first because it is low-risk and cleanly separates macro data from market data.
2. Introduce `tiingo` next for US equities / ETF end-of-day data.
3. Keep `yfinance` as fallback during the transition instead of deleting it.
4. Defer CNH / FX replacement to a later dedicated review.

Conclusion:
- Do **not** do a one-step full replacement of `yfinance`.
- Adopt a **layered source migration**: `FRED` for macro first, `Tiingo` for US EOD second, `yfinance` retained as fallback during transition.

## 2026-05-30: multifactor_volume_price_filter_v1

Change:
- Added a compare-only candidate named `multifactor_volume_price_filter_v1`.
- Registered it under `phase0/strategies/` and enabled it through `walk_forward.strategy_v2.compare_strategies`.
- Reused the existing local-factor building blocks: `quality_growth_score`, residual momentum features, price-volume filters, and the portfolio compare runner.

Strategy logic:
- Stage 1 ranking blends `quality_growth_score`, residual momentum percentile, and low-volatility percentile.
- Stage 2 filtering requires `close > ma20 > ma60`, minimum `amount_ratio20`, capped `upper_shadow_pct`, and optional `breakout20 > 0`.
- Cross-market overlay defaults to `false` for the first validation round.

Parameters:
- `quality_quantiles: [0.7]`
- `residual_windows: [10, 20]`
- `residual_quantiles: [0.6]`
- `top_n_values: [5, 10]`
- `amount_ratio_mins: [1.0, 1.2]`
- `upper_shadow_max_values: [1.0, 1.5]`
- `breakout_required_values: [false, true]`
- Weights: `quality_growth=0.45`, `residual_momentum=0.35`, `low_volatility=0.20`

Reason and reference:
- This is the highest-upside Week 1 candidate and is intended to test whether a modestly richer local-factor composite can improve Sharpe and drawdown without changing the universe score or formal data pipeline.

Latest result:
- Selected candidate remains `legacy_momentum`.
- `multifactor_volume_price_filter_v1`: annualized return mean `-0.0521`, Sharpe mean `-0.4047`, max drawdown mean `-0.0921`, win rate mean `0.2273`.
- Compared with both `residual_momentum_reversal_v1` and `residual_momentum_reversal_v2`, drawdown is materially better, but returns remain negative and the win rate deteriorates sharply.
- Candidate Summary shows only `2` folds, so the result is still weak in sample support.
- Conclusion: do not promote this candidate. It is the least-bad of the new Week 1 compare-only candidates on drawdown, but it still fails as a replacement for `legacy_momentum`.

## 2026-05-30: residual_momentum_reversal_v2

Change:
- Added a compare-only candidate named `residual_momentum_reversal_v2`.
- Registered it under `phase0/strategies/` and enabled it through `walk_forward.strategy_v2.compare_strategies`.
- Kept the existing `residual_momentum_reversal_v1` unchanged as the baseline local-factor comparison candidate.

Strategy logic:
- Retains pool-relative residual momentum and short-horizon reversal as the core ranking logic.
- Adds three anti-overheat filters: minimum `amount_ratio20`, capped `upper_shadow_pct`, and capped `gap_ret`.
- Keeps trend confirmation and volatility filtering.
- Defaults cross-market overlay to `false` for the first validation round.

Parameters:
- `residual_windows: [5, 10, 20]`
- `residual_quantiles: [0.6]`
- `reversal_windows: [1, 3]`
- `reversal_quantiles: [0.7]`
- `amount_ratio_mins: [1.0, 1.2]`
- `upper_shadow_max_values: [1.0, 1.5]`
- `gap_ret_max_values: [0.03, 0.05]`
- `use_xmarket_overlay: false`

Reason and reference:
- This is the next Week 1 candidate after the MA/K baseline.
- It aims to improve the poor risk-adjusted profile of the original residual strategy by filtering short-term overheated names more aggressively without rewriting the entire ranking logic.

Latest result:
- Selected candidate remains `legacy_momentum`.
- `residual_momentum_reversal_v2`: annualized return mean `-0.1167`, Sharpe mean `-0.8768`, max drawdown mean `-0.1740`, win rate mean `0.4126`.
- Compared with `residual_momentum_reversal_v1`, drawdown is slightly better, but annualized return, Sharpe, and win rate all deteriorate, while turnover rises materially.
- Candidate Summary shows only `2` folds, so the result is weak in both quality and sample support.
- Conclusion: do not promote this candidate. Keep it only as a failed refinement of the residual local-factor path.

## 2026-05-30: strategy output standardization

Change:
- Introduced a unified `StrategyOutput` dataclass in `phase0/strategies/base.py`.
- Updated the runner in `phase0/walk_forward.py` to normalize both legacy tuple outputs and structured `StrategyOutput` results.
- Migrated `legacy_momentum`, `ma_kline_baseline_v1`, `quality_growth_price_v1`, and `residual_momentum_reversal_v2` to start emitting standardized strategy outputs with signal frames and metadata.

Reason and reference:
- This is the next natural step after modular strategy extraction. The project now needs a stable downstream interface for future briefs, watchlists, and paper-trade integration, rather than only fold-level metrics.
- Standardized outputs reduce the gap between “strategy used in compare” and “strategy selected for explanation / application layer.”

Latest result:
- Verification run pending.

## 2026-05-30: strategy modularization phase 2 cleanup

Change:
- Removed the old inline implementations in `phase0/walk_forward.py` for:
  - `legacy_momentum`
  - `residual_momentum_reversal_v1`
  - `quality_growth_price_v1`
- Updated compare execution so it now distinguishes single-symbol vs portfolio strategies through `strategy.panel_scope` instead of hardcoding specific strategy names.
- Kept compare/report/effectiveness outputs compatible while further shrinking `walk_forward.py`.

Reason and reference:
- This is the practical second phase of the strategy-building-block refactor.
- The project had already proven that modular strategies could run through compare; the next necessary step was to remove the duplicated inline implementations so `walk_forward.py` stops being both runner and strategy library.

Latest result:
- Verification run completed successfully after cleanup.
- Compare still runs, reports still generate, and the current selected candidate remains `quality_growth_price_v1`.
- The cleanup reduced `phase0/walk_forward.py` significantly while preserving output compatibility.
- Conclusion: the second-stage cleanup is successful. The compare path now depends materially more on the strategy registry and less on inline legacy logic.

## 2026-05-30: quality_growth_price_v1 module extraction

Change:
- Extracted `quality_growth_price_v1` into a dedicated strategy module under `phase0/strategies/quality_growth_price.py`.
- Registered it in `phase0/strategies/__init__.py` and added it to the compare strategy list in `config.yaml`.
- Kept its current strategy logic, parameter search, and report-facing output format compatible with the existing compare/report chain.

Strategy logic:
- Uses `quality_growth_score` as the primary rank score.
- Applies trend confirmation and volatility filtering.
- Keeps target-volatility scaling and optional cross-market overlay support.

Reason and reference:
- This continues the strategy-modularization path so that more candidates can be added without expanding `walk_forward.py` indefinitely.
- `quality_growth_price_v1` was the last major local-factor candidate still implemented inline in `walk_forward.py`.

Latest result:
- Verification run completed successfully after module extraction.
- Current compare reports still generate, and `quality_growth_price_v1` appears in the strategy set without breaking report compatibility.
- The old inline implementation in `walk_forward.py` remains removable in a follow-up cleanup step.

## 2026-05-30: ma_kline_baseline_v1

Change:
- Added a compare-only candidate named `ma_kline_baseline_v1`.
- Registered it under `phase0/strategies/` and enabled it through `walk_forward.strategy_v2.compare_strategies`.
- Reused the shared price/volume feature layer already present in the symbol panel.

Strategy logic:
- Long-only portfolio baseline.
- Entry requires `close > ma20`, `ma20 > ma60`, positive candle body, capped upper shadow, and minimum `amount_ratio20`.
- Eligible names are ranked with a simple blend of `mom20` and `breakout20`.
- Position sizing still follows the existing target-volatility scaling and portfolio cost model.

Parameters:
- `top_n_values: [3, 5]`
- `trend_window_pairs: [[20, 60]]`
- `amount_ratio_mins: [1.0, 1.2]`
- `upper_shadow_max_values: [1.0, 1.5]`

Reason and reference:
- This was the lowest-complexity Week 1 candidate and was intended to provide a diagnostic floor before more complex local-factor candidates are promoted.
- It was chosen first because it could fully reuse the newly added shared price/volume features with minimal additional engineering churn.

Latest result:
- Selected candidate remains `legacy_momentum`.
- `ma_kline_baseline_v1`: annualized return mean `-0.3641`, Sharpe mean `-3.0551`, max drawdown mean `-0.4123`, win rate mean `0.3698`.
- Candidate Summary shows only `2` folds, so the result is weak even before considering the poor performance.
- Conclusion: do not promote this candidate. Keep it only as a failed low-complexity comparison baseline.

## 2026-05-30: candidate sample governance gate

Change:
- Added a candidate-level governance gate to compare mode.
- Candidate `score` remains the raw performance score, while `selection_score` is used for promotion.
- Candidates that do not meet minimum sample support remain visible in reports but receive a promotion-blocking `selection_score`.
- Reports now show `eligible_for_selection`, `governance_reason`, `fold_count`, `symbol_count`, and `panel_scope`.

Governance parameters:
- Symbol-scope candidates require at least `20` fold rows and `20` distinct symbols.
- Portfolio-scope candidates require at least `4` portfolio validation folds.

Reason and reference:
- The latest Phase 0 report selected `quality_growth_price_v1` on raw score with only `2` folds and one `PORTFOLIO` object, while `legacy_momentum` had `228` folds across broad symbol coverage.
- This made the previous ranking structurally biased toward low-sample portfolio candidates.
- The `20` fold / `20` symbol rule is a minimal sanity floor relative to the current `walk_forward_limit: 120` and observed `legacy_momentum` support, not an optimized performance parameter.
- The `4` portfolio-fold rule requires more than two annual validation windows before a portfolio strategy can be promoted, reducing the chance that one favorable market segment drives selection.

Expected result:
- Low-sample candidates can still be researched and shown in reports.
- They cannot become the selected candidate until they meet sample support requirements.

Latest result:
- Full Phase 0 rerun completed after the governance change.
- Selected candidate reverted to `legacy_momentum`, because it is the only current candidate with enough sample support: `228` folds and `118` symbols.
- `quality_growth_price_v1` keeps the highest raw score (`0.8071`) but is blocked from promotion by `portfolio_fold_count<4`.
- Overall effectiveness gate remains `FAIL`: `sharpe_mean = 0.3400` fails `> 0.5`, and `max_drawdown_mean = -0.2995` fails `> -0.25`.
- Conclusion: Phase 0 infrastructure and governance are complete, but the main strategy is no-go and must move into Phase 0.1 improvement.

Implementation note:
- Fixed `multifactor_volume_price_filter_v1` so `apply()` returns `StrategyOutput`, matching the registry runner contract used by the other portfolio strategies.
- This was a compatibility bug fix only; it did not change the strategy's factor logic, entry rules, or parameter grid.

## 2026-05-30: Tushare primary source wiring

Change:
- `phase0.config.load_config()` now loads project `.env` before reading runtime config, so `TUSHARE_TOKEN` stored in ignored local config is available to CLI commands.
- `phase0.data_sources.check_connectivity()` now includes a Tushare `trade_cal` smoke test.
- `phase0 run` now performs a `manual_history_update` pre-run check/update before data-source reporting and walk-forward.
- `config.yaml` enables this through `manual_history_update.run_before_phase0: true`.

Data-source model:
- A-share online primary remains Tushare.
- Backtests and stock-pool construction read from `a_share_history.sqlite` for reproducibility.
- The intended flow is `Tushare -> local SQLite -> walk-forward/report`, not direct per-symbol online fetching during backtest.

Latest result:
- Full Phase 0 rerun with network access completed.
- Tushare smoke test passed: `trade_cal` returned `11` rows, latest date `2026-05-30`.
- yfinance connectivity also passed for configured cross-market targets.
- AkShare connectivity still failed with remote disconnection, confirming it should remain fallback only.
- Manual history pre-run status was `up_to_date`, latest local date `2026-05-29`, so no incremental Tushare write was needed in this run.

## 2026-05-30: US/HK market history split

Change:
- Split the previous generic external-market persistence plan into `us_market_history` and `hk_market_history`.
- Added the US market local SQLite path `data/us_market_history.sqlite` with table `us_daily_bars`.
- Added the HK market local SQLite path `data/hk_market_history.sqlite` with table `hk_daily_bars`, but kept it disabled.
- Walk-forward cross-market overlay now reads US market bars from local SQLite first and does not silently fall back to runtime yfinance unless `runtime_yfinance_fallback` is explicitly enabled.

Reason:
- Current cross-market factors in the strategy are US/ETF/VIX/CNH symbols, so they should be governed as a US market data store instead of a mixed `external_market` bucket.
- HK data is useful for the future product architecture, but it is not yet production-ready in this project. Keeping `hk_market_history.enabled: false` avoids accidentally mounting unvalidated HK data into strategy or report outputs.
- Persisting US bars before walk-forward improves reproducibility because strategy evaluation reads the same local snapshot instead of making ad-hoc online requests during feature construction.

Current status:
- US market provider remains `yfinance` as a transitional source.
- Future upgrade path remains `Tiingo` for US equities/ETF and `FRED` for macro/rate/VIX where applicable.
- HK market will be attached only after source coverage, freshness, adjustment convention, and calendar handling are validated.
