from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pandas as pd

import quant.cli as cli
import quant.cli_commands.pipeline_run as pipeline_run_cli
import quant.cli_commands.reports as report_cli
import quant.reporting.exports as report_exports


def _assert_standard_run(path: Path, *, root: Path, command: str, scope: str) -> None:
    relative = path.relative_to(root)
    parts = relative.parts
    assert parts[0] == "reports"
    assert parts[1] == "runs"
    assert len(parts) >= 5
    assert f"__{command}__{scope}" in parts[3]


def _write_config(path: Path) -> None:
    path.write_text(
        """
quant:
  reporting:
    root_dir: local_reports
    categories:
      phase0: phase_zero
      runs: run_outputs
  local_history: {}
  data_sources: {}
  walk_forward: {}
""",
        encoding="utf-8",
    )


def test_report_export_command_registration_preserves_execution_profile_args() -> None:
    parser = cli.argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="cmd")
    report_cli.register_report_export_commands(subparsers)

    oos_args = parser.parse_args(["oos-report", "--profile", "live", "--output-dir", "out", "--no-enable-limit-check"])
    execution_args = parser.parse_args(["execution-gate", "--profile", "research", "--enable-suspension-check"])

    assert oos_args.cmd == "oos-report"
    assert oos_args.profile == "live"
    assert oos_args.output_dir == "out"
    assert oos_args.enable_limit_check is False
    assert execution_args.cmd == "execution-gate"
    assert execution_args.profile == "research"
    assert execution_args.enable_suspension_check is True


def test_report_export_handler_forwards_bill_args(monkeypatch, tmp_path: Path) -> None:
    calls: list[dict[str, object]] = []
    lines: list[str] = []

    def fake_export_low_turnover_bill(**kwargs):
        calls.append(kwargs)
        return {
            "strategy_id": "demo_strategy",
            "bill": tmp_path / "bill.csv",
            "daily": tmp_path / "daily.csv",
            "preview": tmp_path / "preview.html",
            "rows": 3,
        }

    monkeypatch.setattr(report_cli, "export_low_turnover_bill", fake_export_low_turnover_bill)
    args = SimpleNamespace(
        cmd="bill",
        config=str(tmp_path / "config.yaml"),
        strategy_id="demo_strategy",
        refresh_cache=True,
        no_panel_cache=True,
    )

    exit_code = report_cli.handle_report_export_command(
        args,
        parser=cli.argparse.ArgumentParser(),
        console=SimpleNamespace(print=lambda text: lines.append(str(text))),
    )

    assert exit_code == 0
    assert calls == [
        {
            "config_path": (tmp_path / "config.yaml").resolve(),
            "strategy_id": "demo_strategy",
            "refresh_cache": True,
            "no_panel_cache": True,
        }
    ]
    assert any("Bill export complete" in line for line in lines)
    assert any("Daily assets:" in line for line in lines)


def test_report_export_handler_forwards_execution_profile_args(monkeypatch, tmp_path: Path) -> None:
    calls: list[dict[str, object]] = []
    lines: list[str] = []

    def fake_export_execution_gate(**kwargs):
        calls.append(kwargs)
        return {
            "strategy_id": "demo_strategy",
            "verdict": "pass",
            "folds": 5,
            "report": tmp_path / "execution_gate.md",
        }

    monkeypatch.setattr(report_cli, "export_execution_gate", fake_export_execution_gate)
    args = SimpleNamespace(
        cmd="execution-gate",
        config=str(tmp_path / "config.yaml"),
        strategy_id="demo_strategy",
        profile="live",
        output_dir="custom_output",
        refresh_cache=True,
        no_panel_cache=False,
        slippage=0.002,
        commission=0.0003,
        stamp_duty_sell=0.001,
        price_mode="next_open",
        lot_size=100,
        max_participation_rate=0.08,
        enable_limit_check=False,
        enable_suspension_check=True,
    )

    exit_code = report_cli.handle_report_export_command(
        args,
        parser=cli.argparse.ArgumentParser(),
        console=SimpleNamespace(print=lambda text: lines.append(str(text))),
    )

    assert exit_code == 0
    assert calls == [
        {
            "config_path": (tmp_path / "config.yaml").resolve(),
            "strategy_id": "demo_strategy",
            "profile": "live",
            "output_dir": "custom_output",
            "refresh_cache": True,
            "no_panel_cache": False,
            "slippage": 0.002,
            "commission": 0.0003,
            "stamp_duty_sell": 0.001,
            "price_mode": "next_open",
            "lot_size": 100,
            "max_participation_rate": 0.08,
            "enable_limit_check": False,
            "enable_suspension_check": True,
        }
    ]
    assert any("Account execution gate complete" in line for line in lines)
    assert any("Verdict: pass" in line for line in lines)


def test_cli_main_delegates_top_level_report_export_commands(monkeypatch, tmp_path: Path) -> None:
    calls = []

    def fake_handle_report_export_command(args, *, parser):
        calls.append((args.cmd, Path(args.config), parser is not None))
        return 0

    monkeypatch.setattr(cli, "handle_report_export_command", fake_handle_report_export_command)
    monkeypatch.setattr("sys.argv", ["quant.cli", "bill", "--config", str(tmp_path / "config.yaml")])

    assert cli.main() == 0
    assert calls == [("bill", tmp_path / "config.yaml", True)]


def _assert_configured_run(path: Path, *, root: Path, command: str, scope: str) -> None:
    relative = path.relative_to(root)
    parts = relative.parts
    assert parts[0] == "local_reports"
    assert parts[1] == "run_outputs"
    assert len(parts) >= 5
    assert f"__{command}__{scope}" in parts[3]


def test_low_turnover_bill_defaults_to_standard_run_dir(monkeypatch, tmp_path: Path) -> None:
    calls: list[dict[str, object]] = []

    def fake_export_strategy_bill(**kwargs):
        calls.append(kwargs)
        return {"bill": kwargs["output"], "daily": kwargs["daily_output"], "preview": kwargs["preview_output"]}

    monkeypatch.setattr("quant.reporting.strategy_bill.export_strategy_bill", fake_export_strategy_bill)

    result = report_exports.export_low_turnover_bill(config_path=tmp_path / "config.yaml")

    assert calls
    _assert_standard_run(Path(result["bill"]), root=tmp_path, command="bill", scope="legacy_momentum_low_turnover_v1")
    assert Path(result["daily"]).name == "bill__daily_assets.csv"
    assert Path(result["preview"]).name == "bill__preview.html"


def test_low_turnover_bill_uses_configured_run_dir(monkeypatch, tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    _write_config(config_path)
    calls: list[dict[str, object]] = []

    def fake_export_strategy_bill(**kwargs):
        calls.append(kwargs)
        return {"bill": kwargs["output"], "daily": kwargs["daily_output"], "preview": kwargs["preview_output"]}

    monkeypatch.setattr("quant.reporting.strategy_bill.export_strategy_bill", fake_export_strategy_bill)

    result = report_exports.export_low_turnover_bill(config_path=config_path)

    assert calls
    _assert_configured_run(Path(result["bill"]), root=tmp_path, command="bill", scope="legacy_momentum_low_turnover_v1")


def test_market_regime_defaults_to_standard_run_dir(monkeypatch, tmp_path: Path) -> None:
    calls: list[dict[str, object]] = []

    def fake_export_market_regime_report(**kwargs):
        calls.append(kwargs)
        return {"summary": kwargs["summary_output"], "segments": kwargs["segment_output"], "html": kwargs["html_output"]}

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("quant.reporting.market_regime.export_market_regime_report", fake_export_market_regime_report)

    result = report_exports.export_market_regime_report(root=tmp_path)

    assert calls
    _assert_standard_run(Path(result["summary"]), root=tmp_path, command="market_regime", scope="low_turnover")
    assert Path(result["segments"]).name == "market_regime__segments.csv"
    assert Path(result["html"]).name == "market_regime__report.html"


def test_financial_pti_defaults_to_standard_run_dir(monkeypatch, tmp_path: Path) -> None:
    calls: list[dict[str, object]] = []

    def fake_audit_financial_pti(**kwargs):
        calls.append(kwargs)
        return {"summary": kwargs["summary_output"], "samples": kwargs["sample_output"], "html": kwargs["html_output"]}

    monkeypatch.setattr("quant.data_governance.financial_pti.audit_financial_pti", fake_audit_financial_pti)

    result = report_exports.export_financial_pti(tmp_path / "config.yaml")

    assert calls
    _assert_standard_run(Path(result["summary"]), root=tmp_path, command="financial_pti", scope="qfq_asof")
    assert Path(result["samples"]).name == "financial_pti__problem_samples.csv"
    assert Path(result["html"]).name == "financial_pti__report.html"


def test_universe_pti_defaults_to_standard_run_dir(monkeypatch, tmp_path: Path) -> None:
    calls: list[dict[str, object]] = []

    def fake_audit_universe_pit(**kwargs):
        calls.append(kwargs)
        return {"report": kwargs["report_output"]}

    monkeypatch.setattr("quant.data_governance.universe_pit.audit_universe_pit", fake_audit_universe_pit)

    result = report_exports.export_universe_pit(tmp_path / "config.yaml", as_of_date="2021-05-28")

    assert calls
    _assert_standard_run(Path(result["report"]), root=tmp_path, command="universe_pti", scope="2021_05_28")
    assert Path(result["report"]).name == "universe_pti__report.html"


def test_premarket_defaults_to_standard_run_and_latest(monkeypatch, tmp_path: Path) -> None:
    calls: list[dict[str, object]] = []

    def fake_export_premarket_watchlist(**kwargs):
        calls.append(kwargs)
        return {"watchlist": kwargs["output"], "report": kwargs["report_output"]}

    monkeypatch.setattr("quant.reporting.premarket_watchlist.export_premarket_watchlist", fake_export_premarket_watchlist)

    result = report_exports.export_premarket(config_path=tmp_path / "config.yaml")

    assert calls
    _assert_standard_run(Path(result["watchlist"]), root=tmp_path, command="premarket", scope="watchlist")
    assert Path(result["watchlist"]).name == "premarket__watchlist.csv"
    assert Path(result["report"]).name == "premarket__report.html"
    assert calls[0]["latest_report_output"] == tmp_path / "reports" / "runs" / "latest" / "watchlist" / "index.html"


def test_premarket_account_id_uses_account_scope_and_latest(monkeypatch, tmp_path: Path) -> None:
    calls: list[dict[str, object]] = []

    def fake_export_premarket_watchlist(**kwargs):
        calls.append(kwargs)
        return {"watchlist": kwargs["output"], "report": kwargs["report_output"], "account_id": kwargs["account_id"]}

    monkeypatch.setattr("quant.reporting.premarket_watchlist.export_premarket_watchlist", fake_export_premarket_watchlist)

    result = report_exports.export_premarket(config_path=tmp_path / "config.yaml", account_id="quality")

    assert result["account_id"] == "quality"
    _assert_standard_run(Path(result["watchlist"]), root=tmp_path, command="premarket", scope="quality")
    assert calls[0]["account_id"] == "quality"
    assert calls[0]["latest_report_output"] == tmp_path / "reports" / "runs" / "latest" / "accounts" / "quality" / "watchlist" / "index.html"


def test_premarket_forwards_as_of_date(monkeypatch, tmp_path: Path) -> None:
    calls: list[dict[str, object]] = []

    def fake_export_premarket_watchlist(**kwargs):
        calls.append(kwargs)
        return {"watchlist": kwargs["output"], "report": kwargs["report_output"]}

    monkeypatch.setattr("quant.reporting.premarket_watchlist.export_premarket_watchlist", fake_export_premarket_watchlist)

    report_exports.export_premarket(config_path=tmp_path / "config.yaml", as_of_date="2026-06-30")

    assert calls[0]["as_of_date"] == "2026-06-30"


def test_premarket_uses_configured_run_and_latest(monkeypatch, tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    _write_config(config_path)
    calls: list[dict[str, object]] = []

    def fake_export_premarket_watchlist(**kwargs):
        calls.append(kwargs)
        return {"watchlist": kwargs["output"], "report": kwargs["report_output"]}

    monkeypatch.setattr("quant.reporting.premarket_watchlist.export_premarket_watchlist", fake_export_premarket_watchlist)

    result = report_exports.export_premarket(config_path=config_path)

    assert calls
    _assert_configured_run(Path(result["watchlist"]), root=tmp_path, command="premarket", scope="watchlist")
    assert Path(result["report"]).name == "premarket__report.html"
    assert calls[0]["latest_report_output"] == tmp_path / "local_reports" / "run_outputs" / "latest" / "watchlist" / "index.html"


def test_phase0_cost_sensitivity_compatibility_aliases_new_command_module() -> None:
    assert cli.run_pipeline_cost_sensitivity is pipeline_run_cli.run_pipeline_cost_sensitivity


def test_phase0_cost_sensitivity_uses_configured_phase0_category(monkeypatch, tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    _write_config(config_path)
    saved_paths: list[Path] = []
    report_paths: list[Path] = []

    monkeypatch.setattr(pipeline_run_cli, "configure_local_history", lambda cfg, root: None)
    monkeypatch.setattr(pipeline_run_cli, "configure_akshare_throttle", lambda cfg: None)
    monkeypatch.setattr(pipeline_run_cli, "run_cost_sensitivity", lambda cfg, *, root=None: pd.DataFrame({"scenario": ["base"]}))
    monkeypatch.setattr(pipeline_run_cli, "save_walk_forward_csv", lambda df, output_path: saved_paths.append(Path(output_path)))
    monkeypatch.setattr(pipeline_run_cli, "write_cost_sensitivity_report", lambda path, df: report_paths.append(Path(path)))

    exit_code = pipeline_run_cli.run_pipeline_cost_sensitivity(
        config_path,
        [{"name": "base", "slippage": 0.001, "commission": 0.0, "stamp_duty_sell": 0.0}],
    )

    assert exit_code == 0
    assert saved_paths == [tmp_path / "local_reports" / "phase_zero" / "phase0_cost_sensitivity.csv"]
    assert report_paths == [tmp_path / "local_reports" / "phase_zero" / "phase0_cost_sensitivity_report.md"]


def test_account_bill_defaults_to_standard_run_dir(monkeypatch, tmp_path: Path) -> None:
    class Account:
        account_id = "demo"
        database_path = tmp_path / "account.sqlite"

    account = Account()
    calls: list[dict[str, object]] = []

    monkeypatch.setattr(report_exports, "load_config", lambda path: {"phase0": {}})
    monkeypatch.setattr(report_exports, "load_simulated_accounts", lambda cfg, root: [account])

    def fake_export_account_bill_html(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(report_exports, "export_account_bill_html", fake_export_account_bill_html)

    result = report_exports.export_brief_account_bill(config_path=tmp_path / "config.yaml", brief_date="2026-06-25")

    assert calls
    _assert_standard_run(Path(result["account_bill"]), root=tmp_path, command="brief_account_bill", scope="demo")
    assert Path(result["account_bill"]).name == "account_bill__report.html"


def test_account_bill_can_select_account_id(monkeypatch, tmp_path: Path) -> None:
    class Account:
        def __init__(self, account_id: str) -> None:
            self.account_id = account_id
            self.name = account_id
            self.database_path = tmp_path / f"{account_id}.sqlite"

    accounts = [Account("default"), Account("quality")]
    calls: list[dict[str, object]] = []

    monkeypatch.setattr(report_exports, "load_config", lambda path: {"phase0": {}})
    monkeypatch.setattr(report_exports, "load_simulated_accounts", lambda cfg, root: accounts)

    def fake_export_account_bill_html(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(report_exports, "export_account_bill_html", fake_export_account_bill_html)

    result = report_exports.export_brief_account_bill(
        config_path=tmp_path / "config.yaml",
        account_id="quality",
        brief_date="2026-06-25",
    )

    assert calls[0]["account"].account_id == "quality"
    assert result["account"] == "quality"
    _assert_standard_run(Path(result["account_bill"]), root=tmp_path, command="brief_account_bill", scope="quality")


def test_account_bill_without_daily_rows_exports_placeholder(monkeypatch, tmp_path: Path) -> None:
    class Account:
        account_id = "demo"
        name = "演示账户"
        database_path = tmp_path / "account.sqlite"

    account = Account()

    monkeypatch.setattr(report_exports, "load_config", lambda path: {"reporting": {}})
    monkeypatch.setattr(report_exports, "load_simulated_accounts", lambda cfg, root: [account])

    result = report_exports.export_brief_account_bill(config_path=tmp_path / "config.yaml")
    output = Path(result["account_bill"])
    html = output.read_text(encoding="utf-8")

    assert result["status"] == "empty"
    assert result["brief_date"] == ""
    _assert_standard_run(output, root=tmp_path, command="brief_account_bill", scope="demo")
    assert "暂无确认账单" in html
    assert '<link rel="stylesheet" href="style.css">' in html
    assert (output.parent / "style.css").exists()


def test_cli_report_export_helper_names_remain_compatible() -> None:
    assert cli._export_low_turnover_bill is report_exports.export_low_turnover_bill
    assert cli._export_market_regime_report is report_exports.export_market_regime_report
    assert cli._export_oos_report is report_exports.export_oos_report
    assert cli._export_financial_pti is report_exports.export_financial_pti
    assert cli._export_universe_pit is report_exports.export_universe_pit
    assert cli._export_premarket is report_exports.export_premarket
    assert cli._export_brief_account_bill is report_exports.export_brief_account_bill
    assert cli._export_execution_gate is report_exports.export_execution_gate
