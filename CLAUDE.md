# CLAUDE.md

## Project working baseline

- Treat `DEVELOPMENT_PLAN.md` as the current mainline plan.
- The current mainline goal is to reach a usable A-share quant research and pre-market watchlist product quickly.
- The current product line is: A-share local-factor stock selection + cross-market risk/sentiment overlay + report-style output.
- The main short-term blocker is strategy quality: the main strategy has not yet passed the effectiveness gate, so near-term work should prioritize strategy validation and improvement over platformization.
- Data-source hierarchy is fixed unless the user changes it explicitly:
  - China equities primary: Tushare
  - China equities fallback: AkShare / Sina snapshot / local offline database
  - US equities & ETFs planned primary: Tiingo
  - Macro / rates / VIX planned primary: FRED
  - `yfinance` is fallback only, not a long-term primary source
- Research references under `refdocs/papers/cn/`, `refdocs/papers/en/`, and markdown reports under `reports/` are important development evidence and should be treated as design inputs.
- Files under `refdocs/OUTLOOK/` are long-range outlook only. Do not treat them as current execution scope unless the user explicitly promotes them.
- Keep long-range evolution toward ML research, portfolio construction, and account-level simulation possible, but do not let that derail the current mainline product work.
