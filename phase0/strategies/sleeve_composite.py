from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from phase0.strategies.base import BaseStrategy, StrategyOutput
from phase0.strategies.low_churn_allocator import allocate_low_churn, optional_positive_int
from phase0.strategies.registry import register


def _cross_section_score(series: pd.Series, *, higher_is_better: bool) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce")
    if values.notna().sum() == 0:
        return pd.Series(0.5, index=series.index, dtype=float)
    ranked = values.rank(method="average", ascending=higher_is_better, pct=True)
    return ranked.fillna(0.5).clip(0.0, 1.0)


QUALITY_COMPONENT_COLUMNS = [
    "financial_available_fields",
    "financial_announce_date",
    "quality_growth_score",
    "quality_roe_component",
    "quality_cash_flow_component",
    "quality_profit_growth_component",
    "quality_revenue_growth_component",
    "quality_low_debt_component",
]


def _component_status(frame: pd.DataFrame, fields: list[str], *, required: list[str] | None = None) -> str:
    present = [field for field in fields if field in frame.columns]
    if not present:
        return "degraded:missing_fields"
    required = required or []
    missing_required = [field for field in required if field not in frame.columns]
    if missing_required:
        return "degraded:missing_required=" + ",".join(missing_required)
    values = frame[present].apply(pd.to_numeric, errors="coerce")
    if values.notna().sum().sum() == 0:
        return "degraded:all_nan"
    if values.isna().any().any():
        return "degraded:partial_nan"
    return "ok"


@register
class SleeveCompositeStrategy(BaseStrategy):
    name = "sleeve_composite_v1"
    candidate_name = "sleeve_composite_v1"
    display_name = "Sleeve Composite V1"
    category = "sleeve_composite"
    panel_scope = "portfolio"
    supports_brief = False
    supports_paper_trade = False

    def is_enabled(self, strategy_cfg: dict[str, Any]) -> bool:
        return bool(strategy_cfg.get("sleeve_composite", {}).get("enabled", False))

    def prepare_panel(self, panel: pd.DataFrame, strategy_cfg: dict[str, Any]) -> pd.DataFrame:
        if panel.empty:
            return panel

        from phase0.strategies.quality_low_turnover_monthly import QualityLowTurnoverMonthlyStrategy

        d = QualityLowTurnoverMonthlyStrategy().prepare_panel(panel, strategy_cfg)
        if d.empty:
            return d
        d = d.copy().sort_values(["symbol", "date"]).reset_index(drop=True)
        if "ret" not in d.columns and "close" in d.columns:
            close = pd.to_numeric(d["close"], errors="coerce")
            d["ret"] = close.groupby(d["symbol"]).pct_change().fillna(0.0)

        cfg = strategy_cfg.get("sleeve_composite", {})
        momentum_windows = [int(item) for item in cfg.get("momentum_windows", [20, 60])]
        if "close" in d.columns:
            close = pd.to_numeric(d["close"], errors="coerce")
            for window in momentum_windows:
                col = f"mom{window}"
                if col not in d.columns:
                    d[col] = close.groupby(d["symbol"]).pct_change(window)
        if "vol20" not in d.columns and "ret" in d.columns:
            returns = pd.to_numeric(d["ret"], errors="coerce")
            d["vol20"] = returns.groupby(d["symbol"]).transform(lambda s: s.rolling(20, min_periods=5).std()) * np.sqrt(252)
        return d

    def select_params(
        self,
        train: pd.DataFrame,
        strategy_cfg: dict[str, Any],
        *,
        slippage: float,
        commission: float,
        stamp_duty_sell: float,
    ) -> dict[str, Any]:
        cfg = strategy_cfg.get("sleeve_composite", {})
        raw_weights = dict(
            defensive_quality=float(cfg.get("defensive_quality_weight", 0.55)),
            low_turnover_momentum=float(cfg.get("low_turnover_momentum_weight", 0.25)),
            risk_overlay=float(cfg.get("risk_overlay_weight", 0.20)),
        )
        total = sum(max(value, 0.0) for value in raw_weights.values())
        if total <= 0:
            raw_weights = {"defensive_quality": 0.55, "low_turnover_momentum": 0.25, "risk_overlay": 0.20}
            total = 1.0
        weights = {key: max(value, 0.0) / total for key, value in raw_weights.items()}
        momentum_windows = [int(item) for item in cfg.get("momentum_windows", [20, 60])]
        available_momentum = next((window for window in momentum_windows if f"mom{window}" in train.columns), momentum_windows[0])
        return {
            "eligible": True,
            "defensive_quality_weight": weights["defensive_quality"],
            "low_turnover_momentum_weight": weights["low_turnover_momentum"],
            "risk_overlay_weight": weights["risk_overlay"],
            "momentum_window": int(available_momentum),
            "top_n": int(cfg.get("top_n", 10)),
            "max_symbol_weight": float(cfg.get("max_symbol_weight", 0.10)),
            "train_score": 0.0,
            "train_sharpe": 0.0,
            "train_trades": 0,
        }

    def apply(
        self,
        panel: pd.DataFrame,
        params: dict[str, Any],
        *,
        slippage: float,
        commission: float,
        stamp_duty_sell: float,
    ) -> StrategyOutput:
        if panel.empty:
            empty = pd.Series(dtype=float)
            return StrategyOutput(empty, empty, pd.DataFrame(), self.build_metadata(params))
        if any(col not in panel.columns for col in ["date", "symbol", "ret"]):
            dates = pd.Index(sorted(panel.get("date", pd.Series(dtype=object)).dropna().unique()))
            empty = pd.Series(0.0, index=dates)
            return StrategyOutput(empty, empty, pd.DataFrame(), self.build_metadata(params))

        d = panel.copy().sort_values(["date", "symbol"]).reset_index(drop=True)
        d["defensive_quality_status"] = _component_status(
            d,
            ["quality_growth_score", "vol60", "vol20", "turnover_rate20", "amount_ratio20"],
            required=["quality_growth_score"],
        )
        d["low_turnover_momentum_status"] = _component_status(
            d,
            [f"mom{int(params.get('momentum_window', 20))}", "turnover_rate20", "amount_ratio20"],
            required=[f"mom{int(params.get('momentum_window', 20))}"],
        )
        d["risk_overlay_status"] = _component_status(
            d,
            ["risk_scale", "mapped_xmarket_score", "xmarket_score", "vol60", "vol20"],
        )

        frames: list[pd.DataFrame] = []
        for _, day in d.groupby("date", sort=True):
            day = day.copy()
            quality_parts = []
            if "quality_growth_score" in day.columns:
                quality_parts.append(_cross_section_score(day["quality_growth_score"], higher_is_better=True))
            for col in ["vol60", "vol20"]:
                if col in day.columns:
                    quality_parts.append(_cross_section_score(day[col], higher_is_better=False))
                    break
            for col in ["turnover_rate20", "amount_ratio20"]:
                if col in day.columns:
                    quality_parts.append(_cross_section_score(day[col], higher_is_better=False))
                    break
            day["defensive_quality_score"] = (
                pd.concat(quality_parts, axis=1).mean(axis=1) if quality_parts else pd.Series(0.5, index=day.index)
            )
            if "quality_growth_score" not in day.columns:
                day["defensive_quality_score"] = 0.5

            momentum_parts = []
            mom_col = f"mom{int(params.get('momentum_window', 20))}"
            if mom_col in day.columns:
                momentum_parts.append(_cross_section_score(day[mom_col], higher_is_better=True) * 0.75)
            for col in ["turnover_rate20", "amount_ratio20"]:
                if col in day.columns:
                    momentum_parts.append(_cross_section_score(day[col], higher_is_better=False) * 0.25)
                    break
            day["low_turnover_momentum_score"] = (
                sum(momentum_parts) / sum([0.75 if mom_col in day.columns else 0.0, 0.25 if any(col in day.columns for col in ["turnover_rate20", "amount_ratio20"]) else 0.0])
                if momentum_parts
                else pd.Series(0.5, index=day.index)
            )
            if mom_col not in day.columns:
                day["low_turnover_momentum_score"] = 0.5

            if "risk_scale" in day.columns:
                day["risk_overlay_score"] = pd.to_numeric(day["risk_scale"], errors="coerce").fillna(0.5).clip(0.0, 1.0)
            elif "mapped_xmarket_score" in day.columns:
                day["risk_overlay_score"] = _cross_section_score(day["mapped_xmarket_score"], higher_is_better=True)
            elif "xmarket_score" in day.columns:
                day["risk_overlay_score"] = _cross_section_score(day["xmarket_score"], higher_is_better=True)
            elif "vol60" in day.columns:
                day["risk_overlay_score"] = _cross_section_score(day["vol60"], higher_is_better=False)
            elif "vol20" in day.columns:
                day["risk_overlay_score"] = _cross_section_score(day["vol20"], higher_is_better=False)
            else:
                day["risk_overlay_score"] = 0.5
            day["risk_overlay_scale"] = (
                pd.to_numeric(day["risk_scale"], errors="coerce").fillna(1.0).clip(0.0, 1.0)
                if "risk_scale" in day.columns
                else 1.0
            )

            day["final_score"] = (
                float(params["defensive_quality_weight"]) * day["defensive_quality_score"]
                + float(params["low_turnover_momentum_weight"]) * day["low_turnover_momentum_score"]
                + float(params["risk_overlay_weight"]) * day["risk_overlay_score"]
            )
            frames.append(day)

        out = pd.concat(frames, ignore_index=True)
        out["score"] = out["final_score"]
        out["rank"] = out.groupby("date")["final_score"].rank(method="first", ascending=False)
        top_n = max(1, int(params.get("top_n", 10)))
        max_symbol_weight = max(0.0, float(params.get("max_symbol_weight", 0.10)))
        out["selected"] = ((out["rank"] <= top_n) & out["final_score"].notna()).astype(float)
        selected_count = out.groupby("date")["selected"].transform("sum").replace(0, np.nan)
        out["raw_weight"] = np.minimum(max_symbol_weight, 1.0 / selected_count).fillna(0.0) * out["selected"]
        out["weight_unshifted"] = out["raw_weight"] * pd.to_numeric(out["risk_overlay_scale"], errors="coerce").fillna(1.0)
        out = out.sort_values(["symbol", "date"]).reset_index(drop=True)
        out["weight"] = out.groupby("symbol")["weight_unshifted"].shift(1).fillna(0.0)
        out["position_ret"] = out["weight"] * pd.to_numeric(out["ret"], errors="coerce").fillna(0.0)
        out["sleeve_degradation_reasons"] = out[
            ["defensive_quality_status", "low_turnover_momentum_status", "risk_overlay_status"]
        ].agg(";".join, axis=1)

        weights = out.pivot(index="date", columns="symbol", values="weight").fillna(0.0)
        turnover = weights.diff().abs().sum(axis=1).fillna(weights.abs().sum(axis=1))
        sells = weights.diff().clip(upper=0).abs().sum(axis=1).fillna(0.0)
        gross = out.groupby("date")["position_ret"].sum()
        costs = turnover * (slippage + commission) + sells * stamp_duty_sell
        returns = gross.sub(costs, fill_value=0.0)
        exposure = weights.sum(axis=1)
        columns = [
            "date",
            "symbol",
            "ts_code",
            "defensive_quality_score",
            "low_turnover_momentum_score",
            "risk_overlay_score",
            "risk_overlay_scale",
            "final_score",
            "score",
            "rank",
            "selected",
            "raw_weight",
            "weight_unshifted",
            "weight",
            "ret",
            "position_ret",
            "defensive_quality_status",
            "low_turnover_momentum_status",
            "risk_overlay_status",
            "sleeve_degradation_reasons",
            *QUALITY_COMPONENT_COLUMNS,
        ]
        signal_frame = out[[col for col in columns if col in out.columns]].copy()
        return StrategyOutput(returns=returns, exposure=exposure, signal_frame=signal_frame, metadata=self.build_metadata(params))

    def format_params(self, params: dict[str, Any]) -> str:
        return (
            "sleeve_composite_v1:"
            f"w={params.get('defensive_quality_weight', '')}/"
            f"{params.get('low_turnover_momentum_weight', '')}/"
            f"{params.get('risk_overlay_weight', '')},"
            f"mom{params.get('momentum_window', '')},"
            f"top_n={params.get('top_n', '')},"
            f"max_w={params.get('max_symbol_weight', '')}"
        )


@register
class SleeveCompositeLowChurnStrategy(SleeveCompositeStrategy):
    name = "sleeve_composite_low_churn_v1"
    candidate_name = "sleeve_composite_low_churn_v1"
    display_name = "Sleeve Composite Low Churn V1"
    category = "sleeve_composite_low_churn"
    supports_brief = False
    supports_paper_trade = False

    def is_enabled(self, strategy_cfg: dict[str, Any]) -> bool:
        return bool(strategy_cfg.get("sleeve_composite_low_churn", {}).get("enabled", False))

    def select_params(
        self,
        train: pd.DataFrame,
        strategy_cfg: dict[str, Any],
        *,
        slippage: float,
        commission: float,
        stamp_duty_sell: float,
    ) -> dict[str, Any]:
        params = super().select_params(
            train,
            strategy_cfg,
            slippage=slippage,
            commission=commission,
            stamp_duty_sell=stamp_duty_sell,
        )
        cfg = strategy_cfg.get("sleeve_composite_low_churn", {})
        top_n = int(cfg.get("top_n", params.get("top_n", 10)))
        hold_multiplier = float(cfg.get("hold_rank_multiplier", 2.0))
        params.update(
            {
                "top_n": top_n,
                "buy_top_n": top_n,
                "hold_top_n": max(top_n, int(round(top_n * hold_multiplier))),
                "rebalance_days": max(1, int(cfg.get("rebalance_days", 20))),
                "min_hold_days": max(0, int(cfg.get("min_hold_days", 20))),
                "max_symbol_weight": float(cfg.get("max_symbol_weight", params.get("max_symbol_weight", 0.10))),
                "max_names_per_industry": optional_positive_int(
                    cfg.get(
                        "max_names_per_industry",
                        strategy_cfg.get("constraints", {}).get("industry", {}).get("max_names_per_industry"),
                    )
                ),
            }
        )
        return params

    def apply(
        self,
        panel: pd.DataFrame,
        params: dict[str, Any],
        *,
        slippage: float,
        commission: float,
        stamp_duty_sell: float,
    ) -> StrategyOutput:
        scored = super().apply(
            panel,
            params,
            slippage=0.0,
            commission=0.0,
            stamp_duty_sell=0.0,
        )
        if scored.signal_frame.empty:
            return StrategyOutput(scored.returns, scored.exposure, scored.signal_frame, self.build_metadata(params))

        d = scored.signal_frame.copy().sort_values(["date", "symbol"]).reset_index(drop=True)
        d = _attach_panel_metadata(d, panel, ["industry", "name"])
        columns = [
            "date",
            "symbol",
            "ts_code",
            "defensive_quality_score",
            "low_turnover_momentum_score",
            "risk_overlay_score",
            "risk_overlay_scale",
            "final_score",
            "score",
            "rank",
            "selected",
            "raw_weight",
            "weight_unshifted",
            "weight",
            "held_days",
            "review_reason",
            "ret",
            "position_ret",
            "defensive_quality_status",
            "low_turnover_momentum_status",
            "risk_overlay_status",
            "sleeve_degradation_reasons",
            "industry",
            "name",
            *QUALITY_COMPONENT_COLUMNS,
        ]
        return allocate_low_churn(
            d,
            params=params,
            slippage=slippage,
            commission=commission,
            stamp_duty_sell=stamp_duty_sell,
            signal_columns=columns,
            metadata=self.build_metadata(params),
        )

    def format_params(self, params: dict[str, Any]) -> str:
        return (
            "sleeve_composite_low_churn_v1:"
            f"w={params.get('defensive_quality_weight', '')}/"
            f"{params.get('low_turnover_momentum_weight', '')}/"
            f"{params.get('risk_overlay_weight', '')},"
            f"mom{params.get('momentum_window', '')},"
            f"buy_top={params.get('buy_top_n', params.get('top_n', ''))},"
            f"hold_top={params.get('hold_top_n', '')},"
            f"rebalance={params.get('rebalance_days', '')}d,"
            f"min_hold={params.get('min_hold_days', '')}d,"
            f"max_w={params.get('max_symbol_weight', '')}"
        )


def _attach_panel_metadata(signal: pd.DataFrame, panel: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    if signal.empty or panel.empty or "date" not in signal.columns or "symbol" not in signal.columns:
        return signal
    meta_cols = [col for col in ["date", "symbol", *columns] if col in panel.columns]
    if len(meta_cols) <= 2:
        return signal
    meta = panel[meta_cols].copy()
    meta["date"] = pd.to_datetime(meta["date"], errors="coerce").dt.normalize()
    meta["symbol"] = meta["symbol"].astype(str)
    meta = meta.drop_duplicates(["date", "symbol"])
    out = signal.copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce").dt.normalize()
    out["symbol"] = out["symbol"].astype(str)
    renamed = meta.rename(columns={col: f"__panel_{col}" for col in columns if col in meta.columns})
    out = out.merge(renamed, on=["date", "symbol"], how="left")
    for col in columns:
        panel_col = f"__panel_{col}"
        if panel_col not in out.columns:
            continue
        if col not in out.columns:
            out[col] = out[panel_col]
        else:
            current = out[col]
            missing = current.isna() | current.astype(str).str.strip().eq("")
            out[col] = current.where(~missing, out[panel_col])
    return out.drop(columns=[col for col in out.columns if col.startswith("__panel_")])
