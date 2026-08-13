"""Compare momentum+MACD+MA strategy with vs without event overlay.

Run a single out-of-sample window with fixed params, produce two return curves,
and report whether the event overlay (avoid 首亏, boost 预增) improves returns.

Lightweight: fixed params, no parameter search, one OOS window.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from quant.config import load_config
from quant.strategies.momentum_macd_golden_cross import MomentumMacdGoldenCrossStrategy


def _load_panel(root: Path, config: dict, strategy) -> pd.DataFrame:
    """Load a broad stock panel: universe symbols × N years of daily bars."""
    from quant.walk_forward import _load_symbol
    from quant.universe import load_universe_symbols
    from quant.data_access.local_history import configure_local_history

    # configure local history so _load_symbol reads from the local SQLite DB,
    # not the network (AkShare).
    configure_local_history(config.get("local_history", {}), root)

    years = int(config.get("years", 7))
    symbols = load_universe_symbols(config, root)
    print(f"universe 股票数: {len(symbols)}")
    frames = []
    for sym in symbols:
        df = _load_symbol(sym, years=years, price_adjustment="qfq_current")
        if not df.empty:
            df = df.copy()
            df["symbol"] = sym
            frames.append(df)
    if not frames:
        return pd.DataFrame()
    panel = pd.concat(frames, ignore_index=True)
    return panel


def _run(strategy, panel, params, slippage, commission, stamp_duty_sell):
    out = strategy.apply(panel, params, slippage=slippage, commission=commission, stamp_duty_sell=stamp_duty_sell)
    return out.returns, out.exposure


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    config = load_config(root / "config.yaml")
    wcfg = config.get("walk_forward", {})
    slippage = float(wcfg.get("slippage", 0.001))
    commission = float(wcfg.get("commission", 0.0005))
    stamp = float(wcfg.get("stamp_duty_sell", 0.0005))

    strategy = MomentumMacdGoldenCrossStrategy()
    print("加载面板...")
    panel = _load_panel(root, config, strategy)
    if panel.empty:
        print("面板为空")
        return 1
    print(f"面板: {len(panel)} 行, 列: {list(panel.columns)[:12]}...")

    # prepare (MACD + optional event overlay)
    panel_base = strategy.prepare_panel(panel, {"local_factor": {"momentum_macd_golden_cross": {"enabled": True}}})
    # event overlay version
    panel_event = strategy.prepare_panel(
        panel,
        {"local_factor": {"momentum_macd_golden_cross": {
            "enabled": True,
            "event_overlay": {"enabled": True, "corpus_db": "data/ai_corpus/ai_corpus.sqlite"},
        }}},
    )

    base_params = {
        "eligible": True, "momentum_quantile": 0.6, "momentum_threshold": 0.0,
        "rebalance_days": 5, "top_n": 15, "cross_mode": "any", "require_trend": True,
        "target_vol": 0.18, "max_symbol_weight": 0.10, "use_event_overlay": False,
    }
    event_params = {**base_params, "use_event_overlay": True, "event_boost": 0.02}

    print("\n回测纯策略（动量+金叉+均线）...")
    ret_base, exp_base = _run(strategy, panel_base, base_params, slippage, commission, stamp)

    print("回测叠加事件驱动（避首亏+加预增）...")
    ret_event, exp_event = _run(strategy, panel_event, event_params, slippage, commission, stamp)

    from quant.research.metrics import calc_metrics as _calc_metrics
    m_base = _calc_metrics(ret_base, exp_base)
    m_event = _calc_metrics(ret_event, exp_event)

    print("\n" + "=" * 60)
    print(f"{'指标':<16} {'纯策略':>14} {'叠加事件':>14}")
    print("=" * 60)
    for label, key in [("年化收益", "annualized_return"), ("夏普", "sharpe"), ("最大回撤", "max_drawdown"), ("年化换手", "turnover_annual"), ("交易次数", "trades")]:
        b = m_base.get(key, float("nan"))
        e = m_event.get(key, float("nan"))
        if isinstance(b, float):
            print(f"{label:<16} {b:>14.4f} {e:>14.4f}")
        else:
            print(f"{label:<16} {b!s:>14} {e!s:>14}")
    print("=" * 60)

    # save return curves
    out_dir = root / "reports" / "runs" / pd.Timestamp.now().strftime("%Y-%m-%d")
    out_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"base": ret_base, "event_overlay": ret_event}).to_csv(out_dir / "momentum_event_overlay_comparison.csv")
    print(f"\n收益曲线已保存: {out_dir / 'momentum_event_overlay_comparison.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
