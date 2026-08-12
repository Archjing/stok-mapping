from pathlib import Path

from quant.reporting.premarket_watchlist import _resolve_report_output_template


def test_premarket_default_output_uses_configured_phase0_category(tmp_path: Path) -> None:
    config = {"reporting": {"root_dir": "local_reports", "categories": {"phase0": "phase_zero"}}}
    summary = {"check_time": "2026-06-26 07:30", "signal_date": "2026-06-25"}

    path = _resolve_report_output_template(
        tmp_path,
        config,
        "phase0_premarket_watchlist_{brief_date}.csv",
        summary,
        default_category="phase0",
        explicit=False,
    )

    assert path == tmp_path / "local_reports" / "phase_zero" / "phase0_premarket_watchlist_2026-06-26.csv"


def test_premarket_explicit_output_remains_project_relative(tmp_path: Path) -> None:
    config = {"reporting": {"root_dir": "local_reports", "categories": {"phase0": "phase_zero"}}}
    summary = {"check_time": "2026-06-26 07:30", "signal_date": "2026-06-25"}

    path = _resolve_report_output_template(
        tmp_path,
        config,
        "custom/watchlist_{signal_date}.csv",
        summary,
        default_category="phase0",
        explicit=True,
    )

    assert path == tmp_path / "custom" / "watchlist_2026-06-25.csv"
