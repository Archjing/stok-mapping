"""Cross-Market Semiconductor Timing — Parameter Grid Search.

Grid search: SOX threshold × VIX threshold × position size.
Report top 10 combinations by Sharpe.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from phase0.strategies.cross_market_semiconductor_timing import (
    CrossMarketSemiconductorTimingStrategy,
)
from phase0.research.metrics import annualized_return, max_drawdown, sharpe

s = CrossMarketSemiconductorTimingStrategy()

# Load data
etf = s._load_etf_daily(years=7)
us  = s._load_us_features(years=7)
merged = etf.merge(us, on="date", how="inner").sort_values("date").reset_index(drop=True)
n = len(merged) - 1

sox       = merged["sox_ret"].values[:n]
vix       = merged["vix_close"].values[:n]
open_px   = merged["open"].values[:n]
next_close = merged["close"].values[1:n+1]
timing_ret = next_close / open_px - 1.0

# Costs
SLIP  = 0.001
COMM  = 0.00025
STAMP = 0.0005
RTC   = 2 * SLIP + 2 * COMM + STAMP

# Grid
sox_thresholds  = [0.005, 0.008, 0.01, 0.012, 0.015, 0.02]
vix_thresholds  = [18, 19, 20, 21, 22, 23, 24, 25]
position_sizes  = [0.50, 0.55, 0.60, 0.75, 1.00]

results = []
for sox_t in sox_thresholds:
    for vix_t in vix_thresholds:
        signal = (sox > sox_t) & (vix < vix_t)
        sig_count = signal.sum()
        if sig_count < 10:
            continue
        for pos in position_sizes:
            gross = signal.astype(float) * pos * timing_ret
            net   = gross - signal.astype(float) * pos * RTC
            ret_s = pd.Series(net)
            shp   = sharpe(ret_s)
            ann   = annualized_return(ret_s)
            mdd   = max_drawdown(ret_s)
            wr    = (net[signal] > 0).mean() if sig_count else 0
            results.append({
                "sox_t": sox_t, "vix_t": vix_t, "pos": pos,
                "signals": sig_count, "sharpe": shp, "ann_ret": ann,
                "mdd": mdd, "win_rate": wr,
            })

df = pd.DataFrame(results).sort_values("sharpe", ascending=False)

print("Top 20 by Sharpe (research costs):")
print(f"{'Rank':<5} {'SOX>':<8} {'VIX<':<6} {'Pos':<6} {'Signals':>7} {'Sharpe':>7} {'AnnRet':>8} {'MDD':>8} {'Win%':>6}")
for i, (_, r) in enumerate(df.head(20).iterrows()):
    print(f"{i+1:<5} {r['sox_t']:>6.1%}  {r['vix_t']:>5.0f}  {r['pos']:>4.0%}  "
          f"{int(r['signals']):>7}  {r['sharpe']:>7.2f}  {r['ann_ret']:>7.1%}  "
          f"{r['mdd']:>7.1%}  {r['win_rate']:>5.1%}")

print()
print("Top 20 by Sharpe (NO costs):")
results_nc = []
for sox_t in sox_thresholds:
    for vix_t in vix_thresholds:
        signal = (sox > sox_t) & (vix < vix_t)
        sig_count = signal.sum()
        if sig_count < 10:
            continue
        for pos in position_sizes:
            ret = signal.astype(float) * pos * timing_ret
            ret_s = pd.Series(ret)
            shp = sharpe(ret_s)
            results_nc.append({
                "sox_t": sox_t, "vix_t": vix_t, "pos": pos,
                "signals": sig_count, "sharpe": shp,
                "ann_ret": annualized_return(ret_s),
                "mdd": max_drawdown(ret_s),
            })
df_nc = pd.DataFrame(results_nc).sort_values("sharpe", ascending=False)
for i, (_, r) in enumerate(df_nc.head(20).iterrows()):
    print(f"{i+1:<5} {r['sox_t']:>6.1%}  {r['vix_t']:>5.0f}  {r['pos']:>4.0%}  "
          f"{int(r['signals']):>7}  {r['sharpe']:>7.2f}  {r['ann_ret']:>7.1%}  "
          f"{r['mdd']:>7.1%}")

# Best with costs, 55% pos
print()
print("Best with costs, pos=55%:")
df_55 = df[df["pos"] == 0.55].head(10)
for i, (_, r) in enumerate(df_55.iterrows()):
    print(f"  SOX>{r['sox_t']:.1%} VIX<{r['vix_t']:.0f}: "
          f"Sharpe={r['sharpe']:.2f} Ret={r['ann_ret']:.1%} MDD={r['mdd']:.1%} "
          f"Sig={int(r['signals'])}")
