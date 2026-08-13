"""Robustness deep-dive on the fed-funds rate signal for style rotation.

Checks:
1. parameter robustness: change signal lookback (1/3/6/12m), threshold direction
2. sub-period stability: split 2015-2026 into two halves
3. combination: fed-funds signal + price momentum (RS MA) — does macro + price
   beat either alone?
4. comparison: level vs change (rate LEVEL high→value vs CHANGE rising→value)

All monthly, T+1 execution, cost 0.1% per switch. Research layer only.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.backtest_macro_rotation import load_style_monthly_returns, load_macro_monthly


def _metrics_monthly(ret: pd.Series) -> dict:
    ann = (1 + ret.mean()) ** 12 - 1
    sharpe = ret.mean() / ret.std() * np.sqrt(12) if ret.std() > 0 else 0.0
    equity = (1 + ret).cumprod()
    mdd = (equity / equity.cummax() - 1).min()
    return {"annual_return": ann, "sharpe": sharpe, "max_drawdown": mdd}


def _run(style: pd.DataFrame, w: pd.Series, cost: float = 0.001) -> dict:
    w = w.shift(1).fillna(0.5).clip(0.0, 1.0)
    ret = w * style["growth_ret"] + (1 - w) * style["value_ret"]
    turnover = w.diff().abs().fillna(0.0)
    ret = ret - turnover * cost
    m = _metrics_monthly(ret)
    m["n_switches"] = int((w.diff().abs() > 0.5).sum())
    return m


def _fed_signal(macro: pd.DataFrame, lookback: int = 3, mode: str = "change") -> pd.Series:
    """mode='change': rising rate → value; mode='level': high rate → value (threshold=median)."""
    s = macro["US_FED_FUNDS"]
    if mode == "change":
        w = (s.diff(lookback) < 0).astype(float)  # falling → growth
    else:
        w = (s < s.median()).astype(float)  # below-median rate → growth
    w = w.mask(s.isna(), 0.5)
    return w.reindex(macro.index).fillna(0.5)


def main() -> None:
    style = load_style_monthly_returns()
    macro = load_macro_monthly()
    idx = style.index.intersection(macro.index)
    style = style.loc[idx]
    macro = macro.loc[idx]
    start = pd.Timestamp("2015-03-01")
    style = style[style.index >= start]
    macro = macro[macro.index >= start]

    # baseline
    base_g = pd.Series(1.0, index=style.index)
    base_v = pd.Series(0.0, index=style.index)
    base_5050 = pd.Series(0.5, index=style.index)
    print(f"样本: {style.index.min().date()} ~ {style.index.max().date()} ({len(style)} 月)\n")

    rows = []
    rows.append({"name": "持有成长", **_run(style, base_g)})
    rows.append({"name": "持有价值", **_run(style, base_v)})
    rows.append({"name": "50/50", **_run(style, base_5050)})

    # 1. parameter robustness: lookback sweep
    print("=== 1. 参数稳健性：信号回看窗口 ===")
    for lb in [1, 3, 6, 12]:
        w = _fed_signal(macro, lookback=lb)
        rows.append({"name": f"美联邦基金利率 change@lookback{lb}m", **_run(style, w)})

    # 2. level vs change
    print("=== 2. 水平 vs 变化 ===")
    w = _fed_signal(macro, mode="level")
    rows.append({"name": "美联邦基金利率 level(低于中位=成长)", **_run(style, w)})

    # 3. sub-period stability
    print("=== 3. 分时段稳定性 ===")
    split = pd.Timestamp("2020-12-31")
    for label, sub in [("2015-2020", style[style.index <= split]), ("2021-2026", style[style.index > split])]:
        sub_macro = macro.loc[sub.index]
        w = _fed_signal(sub_macro, lookback=3)
        m = _run(sub, w)
        m["name"] = f"美联邦基金利率 change@3m ({label})"
        rows.append(m)

    # 4. combination with price momentum (RS MA)
    print("=== 4. 与价格动量组合 ===")
    rs = np.log(bmr._load_index_monthly_safe() if False else None) if False else None
    # price momentum on RS: use style returns to build RS, then RS>MA(60)
    # (reuse the daily logic but at monthly frequency)
    from scripts.backtest_style_rotation import load_style_prices
    g, v = load_style_prices()
    rs_daily = np.log(g / v)
    rs_monthly = rs_daily.resample("ME").last()
    rs_monthly = rs_monthly.reindex(style.index)
    ma_rs = rs_monthly.rolling(3).mean()
    w_price = (rs_monthly > ma_rs).astype(float).reindex(style.index).fillna(0.5)

    w_macro = _fed_signal(macro, lookback=3)
    # combination: both agree → strong; disagree → neutral 0.5
    w_comb = ((w_macro > 0.5) & (w_price > 0.5)).astype(float)
    w_comb = w_comb.mask((w_macro < 0.5) & (w_price < 0.5), 0.0)
    rows.append({"name": "价格动量 RS>MA3", **_run(style, w_price)})
    rows.append({"name": "组合:利率+价格动量", **_run(style, w_comb)})

    df = pd.DataFrame(rows)
    df["年化"] = df["annual_return"].map(lambda x: f"{x*100:.1f}%")
    df["夏普"] = df["sharpe"].map(lambda x: f"{x:.2f}")
    df["回撤"] = df["max_drawdown"].map(lambda x: f"{x*100:.1f}%")
    df["切换"] = df["n_switches"]
    print("\n" + df[["name", "年化", "夏普", "回撤", "切换"]].to_string(index=False))


if __name__ == "__main__":
    main()
