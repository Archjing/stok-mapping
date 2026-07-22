from __future__ import annotations

import copy
from typing import Any

import pandas as pd

from phase0.data_access.daily_basic_history import merge_point_in_time_daily_basic
from phase0.research.factors import DEFAULT_WEIGHTS, add_slow_multifactor_features
from phase0.strategies.base import BaseStrategy, StrategyOutput
from phase0.strategies.low_churn_allocator import allocate_low_churn
from phase0.strategies.registry import register
from phase0.strategies.sleeve_composite import QUALITY_COMPONENT_COLUMNS, SleeveCompositeStrategy


SLOW_SCORE_COLUMNS = [
    "slow_quality_score",
    "slow_earnings_score",
    "slow_value_score",
    "slow_low_vol_score",
    "slow_residual_momentum_score",
]
REQUIRED_SLOW_COLUMNS = [
    *SLOW_SCORE_COLUMNS,
    "slow_factor_available_count",
    "slow_composite_score",
]


@register
class SleeveCompositeLowChurnV2Strategy(BaseStrategy):
    name = "sleeve_composite_low_churn_v2"
    candidate_name = "sleeve_composite_low_churn_v2"
    display_name = "Sleeve Composite Low Churn V2"
    category = "sleeve_composite_low_churn_v2"
    panel_scope = "portfolio"
    supports_brief = False
    supports_paper_trade = False

    def is_enabled(self, strategy_cfg: dict[str, Any]) -> bool:
        return bool(strategy_cfg.get("sleeve_composite_low_churn_v2", {}).get("enabled", False))

    def prepare_panel(self, panel: pd.DataFrame, strategy_cfg: dict[str, Any]) -> pd.DataFrame:
        if panel.empty:
            return panel

        prepared_cfg = copy.deepcopy(strategy_cfg)
        quality_cfg = prepared_cfg.setdefault("local_factor", {}).setdefault("quality_growth", {})
        quality_cfg["enabled"] = True
        prepared = SleeveCompositeStrategy().prepare_panel(panel, prepared_cfg)
        if prepared.empty:
            return prepared

        cfg = strategy_cfg.get("sleeve_composite_low_churn_v2", {})
        prepared = merge_point_in_time_daily_basic(
            prepared,
            as_of_date=prepared["date"].max(),
            market=str(cfg.get("market", "CN")),
            table=str(cfg.get("daily_basic_table", cfg.get("table", "market_daily_basic"))),
        )
        weights = cfg.get("factor_weights", DEFAULT_WEIGHTS)
        min_available = max(
            1,
            int(cfg.get("min_available", cfg.get("min_available_factors", 4))),
        )
        return add_slow_multifactor_features(
            prepared,
            weights=weights,
            min_available_factors=min_available,
        )

    def select_params(
        self,
        train: pd.DataFrame,
        strategy_cfg: dict[str, Any],
        *,
        slippage: float,
        commission: float,
        stamp_duty_sell: float,
    ) -> dict[str, Any]:
        del train, slippage, commission, stamp_duty_sell
        cfg = strategy_cfg.get("sleeve_composite_low_churn_v2", {})
        raw_weights = cfg.get("factor_weights", DEFAULT_WEIGHTS)
        weights = {str(column): max(float(weight), 0.0) for column, weight in raw_weights.items()}
        total = float(sum(weights.values()))
        if total <= 0 or pd.isna(total):
            raise ValueError("slow multifactor weights must have a positive total")
        factor_weights = {column: weight / total for column, weight in weights.items()}

        buy_top_n = max(1, int(cfg.get("buy_top_n", cfg.get("top_n", 30))))
        hold_top_n = max(buy_top_n, int(cfg.get("hold_top_n", 50)))
        return {
            "eligible": True,
            "factor_weights": factor_weights,
            "min_available_factors": max(
                1,
                int(cfg.get("min_available", cfg.get("min_available_factors", 4))),
            ),
            "top_n": buy_top_n,
            "buy_top_n": buy_top_n,
            "hold_top_n": hold_top_n,
            "rebalance_days": max(20, int(cfg.get("rebalance_days", 20))),
            "min_hold_days": max(20, int(cfg.get("min_hold_days", 20))),
            "max_symbol_weight": min(1.0, max(0.0, float(cfg.get("max_symbol_weight", 0.04)))),
            "max_names_per_industry": max(1, int(cfg.get("max_names_per_industry", 3))),
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
        metadata = self.build_metadata(params)
        if panel.empty or not bool(params.get("eligible", True)):
            empty = pd.Series(dtype=float)
            return StrategyOutput(empty, empty, pd.DataFrame(), metadata)

        required_columns = ["date", "symbol", "ret", *REQUIRED_SLOW_COLUMNS]
        if any(column not in panel.columns for column in required_columns):
            dates = pd.Index(sorted(panel.get("date", pd.Series(dtype=object)).dropna().unique()))
            zero = pd.Series(0.0, index=dates)
            return StrategyOutput(zero, zero.copy(), pd.DataFrame(), metadata)

        scored = panel.copy().sort_values(["date", "symbol"]).reset_index(drop=True)
        scored["final_score"] = pd.to_numeric(scored["slow_composite_score"], errors="coerce")
        scored["score"] = scored["final_score"]
        if "risk_scale" in scored.columns:
            risk_scale = pd.to_numeric(scored["risk_scale"], errors="coerce")
        else:
            risk_scale = pd.Series(1.0, index=scored.index, dtype=float)
        scored["risk_overlay_scale"] = risk_scale.fillna(1.0).clip(0.0, 1.0)

        signal_columns = [
            "date",
            "symbol",
            "ts_code",
            "industry",
            "name",
            *REQUIRED_SLOW_COLUMNS,
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
            *QUALITY_COMPONENT_COLUMNS,
        ]
        return allocate_low_churn(
            scored,
            params=params,
            slippage=slippage,
            commission=commission,
            stamp_duty_sell=stamp_duty_sell,
            signal_columns=signal_columns,
            metadata=metadata,
        )

    def format_params(self, params: dict[str, Any]) -> str:
        weights = params.get("factor_weights", {})
        ordered_columns = [column for column in DEFAULT_WEIGHTS if column in weights]
        ordered_columns.extend(sorted(set(weights).difference(ordered_columns)))
        formatted_weights = "/".join(
            f"{column}:{float(weights[column]):g}" for column in ordered_columns
        )
        return (
            "sleeve_composite_low_churn_v2:"
            f"w={formatted_weights},"
            f"buy_top={params.get('buy_top_n', params.get('top_n', ''))},"
            f"hold_top={params.get('hold_top_n', '')},"
            f"rebalance={params.get('rebalance_days', '')}d,"
            f"min_hold={params.get('min_hold_days', '')}d,"
            f"max_w={params.get('max_symbol_weight', '')},"
            f"industry_cap={params.get('max_names_per_industry', '')}"
        )
