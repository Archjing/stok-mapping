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
