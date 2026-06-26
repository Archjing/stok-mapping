from __future__ import annotations

import phase0.strategy_admission as admission
from phase0.research.admission import review


def test_admission_review_helpers_are_reexported_from_runner() -> None:
    assert admission._attach_price_adjustment_status is review.attach_price_adjustment_status
    assert admission._build_window_matrix is review.build_window_matrix
    assert admission._window_metrics is review.window_metrics
    assert admission._build_constraint_review is review.build_constraint_review
    assert admission._admission_action is review.admission_action
    assert admission._parameter_unstable_window_count is review.parameter_unstable_window_count
    assert admission._industry_concentration_window_count is review.industry_concentration_window_count
    assert admission._industry_missing_window_count is review.industry_missing_window_count
    assert admission._factor_missing_window_count is review.factor_missing_window_count
    assert admission._price_adjustment_fail_window_count is review.price_adjustment_fail_window_count
    assert admission._turnover_fail_window_count is review.turnover_fail_window_count
