from __future__ import annotations

import argparse
from pathlib import Path
from types import SimpleNamespace

import phase0.cli as cli
import phase0.cli_commands.research as research_cli


def _silent_console() -> SimpleNamespace:
    return SimpleNamespace(print=lambda text: None)


def test_research_command_registration_preserves_args() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="cmd")
    research_cli.register_research_commands(subparsers)

    market_args = parser.parse_args(["strategy-market-context", "--fold-attribution", "folds.csv"])
    core_args = parser.parse_args(
        [
            "strategy-core-reachability-diagnostic",
            "--candidate-folds",
            "candidate_folds.csv",
            "--output-dir",
            "out",
            "--seed-benchmark-core",
        ]
    )
    role_args = parser.parse_args(
        [
            "strategy-role-card",
            "--strategy",
            "sample_strategy",
            "--matrix",
            "matrix.csv",
            "--constraints",
            "constraints.csv",
            "--output-dir",
            "role_card",
        ]
    )

    assert market_args.cmd == "strategy-market-context"
    assert market_args.config == "config.yaml"
    assert market_args.fold_attribution == "folds.csv"
    assert market_args.trend_window == 120
    assert market_args.vol_quantile == 0.70
    assert core_args.cmd == "strategy-core-reachability-diagnostic"
    assert core_args.seed_benchmark_core is True
    assert core_args.core_top_n == 60
    assert core_args.output_dir == "out"
    assert role_args.cmd == "strategy-role-card"
    assert role_args.strategy == "sample_strategy"
    assert role_args.matrix == "matrix.csv"
    assert role_args.constraints == "constraints.csv"


def test_market_context_handler_configures_local_history_and_forwards_args(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    def fake_load_config(path: Path) -> dict[str, object]:
        calls.append(("load_config", {"path": path}))
        return {"phase0": {"local_history": {"path": "history.sqlite"}, "benchmark_symbol": "SH.000300"}}

    def fake_configure_local_history(raw: dict[str, object], root: Path) -> None:
        calls.append(("configure_local_history", {"raw": raw, "root": root}))

    def fake_run_strategy_market_context(**kwargs):
        calls.append(("run_strategy_market_context", kwargs))
        return SimpleNamespace(
            benchmark_symbol="SH.000300",
            rows=3,
            csv_path=tmp_path / "context.csv",
            summary_csv_path=tmp_path / "summary.csv",
            coverage_csv_path=tmp_path / "coverage.csv",
            md_path=tmp_path / "context.md",
        )

    monkeypatch.setattr(research_cli, "load_config", fake_load_config)
    monkeypatch.setattr(research_cli, "configure_local_history", fake_configure_local_history)
    monkeypatch.setattr(research_cli, "run_strategy_market_context", fake_run_strategy_market_context)

    args = SimpleNamespace(
        cmd="strategy-market-context",
        config=str(tmp_path / "config.yaml"),
        fold_attribution=str(tmp_path / "folds.csv"),
        output_dir=str(tmp_path / "market_context"),
        benchmark_symbol="SH.000300",
        trend_window=100,
        vol_window=15,
        vol_quantile=0.8,
    )

    exit_code = research_cli.handle_research_command(
        args,
        parser=argparse.ArgumentParser(),
        console=_silent_console(),
    )

    assert exit_code == 0
    assert calls[0] == ("load_config", {"path": (tmp_path / "config.yaml").resolve()})
    assert calls[1] == (
        "configure_local_history",
        {"raw": {"path": "history.sqlite"}, "root": tmp_path},
    )
    assert calls[2] == (
        "run_strategy_market_context",
        {
            "config": {"local_history": {"path": "history.sqlite"}, "benchmark_symbol": "SH.000300"},
            "root": tmp_path,
            "fold_attribution_path": (tmp_path / "folds.csv").resolve(),
            "output_dir": (tmp_path / "market_context").resolve(),
            "benchmark_symbol": "SH.000300",
            "trend_window": 100,
            "vol_window": 15,
            "vol_quantile": 0.8,
        },
    )


def test_exposure_handler_forwards_command_and_paths(monkeypatch, tmp_path: Path) -> None:
    calls: list[dict[str, object]] = []

    def fake_load_config(path: Path) -> dict[str, object]:
        return {"phase0": {"local_history": {}}}

    def fake_run_strategy_exposure_diagnostic(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            rows=10,
            strong_lag_rows=2,
            csv_path=tmp_path / "exposure.csv",
            summary_csv_path=tmp_path / "summary.csv",
            run_log_md_path=tmp_path / "run_log.md",
            md_path=tmp_path / "exposure.md",
        )

    monkeypatch.setattr(research_cli, "load_config", fake_load_config)
    monkeypatch.setattr(research_cli, "run_strategy_exposure_diagnostic", fake_run_strategy_exposure_diagnostic)
    monkeypatch.setattr(
        research_cli.os,
        "sys",
        SimpleNamespace(argv=["phase0.cli", "strategy-exposure-diagnostic", "--candidate-folds", "folds.csv"]),
    )

    args = SimpleNamespace(
        cmd="strategy-exposure-diagnostic",
        config=str(tmp_path / "config.yaml"),
        candidate_folds=str(tmp_path / "candidate_folds.csv"),
        market_context=str(tmp_path / "market_context.csv"),
        universe=str(tmp_path / "universe.csv"),
        output_dir=str(tmp_path / "exposure"),
    )

    exit_code = research_cli.handle_research_command(
        args,
        parser=argparse.ArgumentParser(),
        console=_silent_console(),
    )

    assert exit_code == 0
    assert calls == [
        {
            "config": {"local_history": {}},
            "root": tmp_path,
            "config_path": (tmp_path / "config.yaml").resolve(),
            "candidate_folds_path": (tmp_path / "candidate_folds.csv").resolve(),
            "market_context_path": (tmp_path / "market_context.csv").resolve(),
            "universe_path": (tmp_path / "universe.csv").resolve(),
            "output_dir": (tmp_path / "exposure").resolve(),
            "command": "phase0.cli strategy-exposure-diagnostic --candidate-folds folds.csv",
        }
    ]


def test_fold_attribution_handler_forwards_paths(monkeypatch, tmp_path: Path) -> None:
    calls: list[dict[str, object]] = []

    def fake_run_strategy_fold_attribution(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            paired_rows=5,
            paired_fold_csv_path=tmp_path / "paired.csv",
            daily_exposure_csv_path=tmp_path / "daily.csv",
            top_holding_csv_path=tmp_path / "top.csv",
            quality_bucket_csv_path=tmp_path / "quality.csv",
            turnover_cost_csv_path=tmp_path / "turnover.csv",
            md_path=tmp_path / "fold.md",
        )

    monkeypatch.setattr(research_cli, "run_strategy_fold_attribution", fake_run_strategy_fold_attribution)

    args = SimpleNamespace(
        cmd="strategy-fold-attribution",
        quality_fold_attribution=str(tmp_path / "quality_fold.csv"),
        price_volume_fold_attribution=str(tmp_path / "price_fold.csv"),
        quality_market_context=str(tmp_path / "quality_market.csv"),
        price_volume_market_context=str(tmp_path / "price_market.csv"),
        quality_holdings=str(tmp_path / "quality_holdings.csv"),
        price_volume_holdings=str(tmp_path / "price_holdings.csv"),
        quality_daily_exposure=str(tmp_path / "quality_daily.csv"),
        price_volume_daily_exposure=str(tmp_path / "price_daily.csv"),
        output_dir=str(tmp_path / "fold_attr"),
    )

    exit_code = research_cli.handle_research_command(
        args,
        parser=argparse.ArgumentParser(),
        console=_silent_console(),
    )

    assert exit_code == 0
    assert calls == [
        {
            "quality_fold_attribution_path": (tmp_path / "quality_fold.csv").resolve(),
            "price_volume_fold_attribution_path": (tmp_path / "price_fold.csv").resolve(),
            "quality_market_context_path": (tmp_path / "quality_market.csv").resolve(),
            "price_volume_market_context_path": (tmp_path / "price_market.csv").resolve(),
            "quality_holdings_path": (tmp_path / "quality_holdings.csv").resolve(),
            "price_volume_holdings_path": (tmp_path / "price_holdings.csv").resolve(),
            "quality_daily_exposure_path": (tmp_path / "quality_daily.csv").resolve(),
            "price_volume_daily_exposure_path": (tmp_path / "price_daily.csv").resolve(),
            "output_dir": (tmp_path / "fold_attr").resolve(),
        }
    ]


def test_cli_main_delegates_research_commands(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[str, bool]] = []

    def fake_handle_research_command(args, *, parser):
        calls.append((args.cmd, parser is not None))
        return 0

    monkeypatch.setattr(cli, "handle_research_command", fake_handle_research_command)
    monkeypatch.setattr(
        "sys.argv",
        [
            "phase0.cli",
            "strategy-role-card",
            "--strategy",
            "sample_strategy",
            "--matrix",
            str(tmp_path / "matrix.csv"),
            "--constraints",
            str(tmp_path / "constraints.csv"),
            "--output-dir",
            str(tmp_path / "role_card"),
        ],
    )

    assert cli.main() == 0
    assert calls == [("strategy-role-card", True)]
