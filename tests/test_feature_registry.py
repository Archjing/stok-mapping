"""Tests for the metadata-only feature registry."""
from __future__ import annotations

import pandas as pd
import pytest

from quant.research.features.registry import FeatureRegistry, FeatureSpec


def _ret1_spec() -> FeatureSpec:
    return FeatureSpec(
        name="ret_1", version="1", inputs=("close",),
        lookback_sessions=1, availability_lag_sessions=0,
        missing_data_policy="preserve_nan",
        builder=lambda frame: frame["close"].pct_change(),
    )


def test_registry_rejects_unknown_dependency() -> None:
    registry = FeatureRegistry()
    with pytest.raises(ValueError, match="unknown dependency"):
        registry.register(FeatureSpec(
            name="bad", version="1", inputs=("missing",),
            lookback_sessions=1, availability_lag_sessions=0,
            missing_data_policy="preserve_nan", builder=lambda frame: frame["close"],
        ))


def test_registry_rejects_duplicate_name() -> None:
    registry = FeatureRegistry.with_base_fields({"close"})
    registry.register(_ret1_spec())
    with pytest.raises(ValueError, match="duplicate feature"):
        registry.register(_ret1_spec())


def test_registry_resolves_dependency_before_requested_feature() -> None:
    registry = FeatureRegistry.with_base_fields({"close"})
    registry.register(_ret1_spec())
    registry.register(FeatureSpec(
        name="ret_5", version="1", inputs=("ret_1",),
        lookback_sessions=5, availability_lag_sessions=0,
        missing_data_policy="preserve_nan",
        builder=lambda frame: frame["ret_1"].rolling(5).sum(),
    ))
    assert registry.resolve(("ret_5",)) == ("ret_1", "ret_5")


def test_registry_rejects_self_reference() -> None:
    registry = FeatureRegistry.with_base_fields({"close"})
    with pytest.raises(ValueError, match="unknown dependency"):
        registry.register(FeatureSpec(
            name="a", version="1", inputs=("a",), lookback_sessions=1,
            availability_lag_sessions=0, missing_data_policy="preserve_nan",
            builder=lambda frame: frame["close"],
        ))


def test_build_is_pure_and_preserves_input() -> None:
    registry = FeatureRegistry.with_base_fields({"close"})
    registry.register(_ret1_spec())
    panel = pd.DataFrame({
        "symbol": ["A", "A", "B", "B"],
        "date": pd.date_range("2024-01-01", periods=4),
        "close": [10.0, 11.0, 20.0, 22.0],
    }).set_index(["symbol", "date"])
    original = panel.copy(deep=True)
    result = registry.build(panel, ("ret_1",))
    assert "ret_1" in result.columns
    pd.testing.assert_frame_equal(panel, original)  # input unchanged
    assert list(result.columns) == ["close", "ret_1"]


def test_build_rejects_misaligned_output() -> None:
    registry = FeatureRegistry.with_base_fields({"close"})
    registry.register(FeatureSpec(
        name="bad_align", version="1", inputs=("close",),
        lookback_sessions=1, availability_lag_sessions=0,
        missing_data_policy="preserve_nan",
        builder=lambda frame: pd.Series([1.0], index=[999]),
    ))
    panel = pd.DataFrame({
        "symbol": ["A"], "date": pd.to_datetime(["2024-01-01"]), "close": [10.0],
    }).set_index(["symbol", "date"])
    with pytest.raises(ValueError, match="misaligned builder output"):
        registry.build(panel, ("bad_align",))


def test_spec_validation() -> None:
    with pytest.raises(ValueError, match="missing_data_policy"):
        FeatureSpec(
            name="x", version="1", inputs=("close",), lookback_sessions=1,
            availability_lag_sessions=0, missing_data_policy="bogus",
            builder=lambda frame: frame["close"],
        )
