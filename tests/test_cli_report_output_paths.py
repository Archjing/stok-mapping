from __future__ import annotations

from pathlib import Path

import phase0.cli as cli


def _assert_standard_run(path: Path, *, root: Path, command: str, scope: str) -> None:
    relative = path.relative_to(root)
    parts = relative.parts
    assert parts[0] == "reports"
    assert parts[1] == "runs"
    assert len(parts) >= 5
    assert f"__{command}__{scope}" in parts[3]


def test_low_turnover_bill_defaults_to_standard_run_dir(monkeypatch, tmp_path: Path) -> None:
    calls: list[dict[str, object]] = []

    def fake_export_strategy_bill(**kwargs):
        calls.append(kwargs)
        return {"bill": kwargs["output"], "daily": kwargs["daily_output"], "preview": kwargs["preview_output"]}

    monkeypatch.setattr("scripts.export_strategy_bill.export_strategy_bill", fake_export_strategy_bill)

    result = cli._export_phase0_low_turnover_bill(config_path=tmp_path / "config.yaml")

    assert calls
    _assert_standard_run(Path(result["bill"]), root=tmp_path, command="bill", scope="legacy_momentum_low_turnover_v1")
    assert Path(result["daily"]).name == "bill__daily_assets.csv"
    assert Path(result["preview"]).name == "bill__preview.html"


def test_market_regime_defaults_to_standard_run_dir(monkeypatch, tmp_path: Path) -> None:
    calls: list[dict[str, object]] = []

    def fake_export_market_regime_report(**kwargs):
        calls.append(kwargs)
        return {"summary": kwargs["summary_output"], "segments": kwargs["segment_output"], "html": kwargs["html_output"]}

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("scripts.export_market_regime_report.export_market_regime_report", fake_export_market_regime_report)

    result = cli._export_phase0_market_regime_report(root=tmp_path)

    assert calls
    _assert_standard_run(Path(result["summary"]), root=tmp_path, command="market_regime", scope="low_turnover")
    assert Path(result["segments"]).name == "market_regime__segments.csv"
    assert Path(result["html"]).name == "market_regime__report.html"


def test_financial_pti_defaults_to_standard_run_dir(monkeypatch, tmp_path: Path) -> None:
    calls: list[dict[str, object]] = []

    def fake_audit_financial_pti(**kwargs):
        calls.append(kwargs)
        return {"summary": kwargs["summary_output"], "samples": kwargs["sample_output"], "html": kwargs["html_output"]}

    monkeypatch.setattr("scripts.audit_financial_pti.audit_financial_pti", fake_audit_financial_pti)

    result = cli._export_phase0_financial_pti(tmp_path / "config.yaml")

    assert calls
    _assert_standard_run(Path(result["summary"]), root=tmp_path, command="financial_pti", scope="qfq_asof")
    assert Path(result["samples"]).name == "financial_pti__problem_samples.csv"
    assert Path(result["html"]).name == "financial_pti__report.html"


def test_universe_pti_defaults_to_standard_run_dir(monkeypatch, tmp_path: Path) -> None:
    calls: list[dict[str, object]] = []

    def fake_audit_universe_pit(**kwargs):
        calls.append(kwargs)
        return {"report": kwargs["report_output"]}

    monkeypatch.setattr("scripts.audit_universe_pit.audit_universe_pit", fake_audit_universe_pit)

    result = cli._export_phase0_universe_pit(tmp_path / "config.yaml", as_of_date="2021-05-28")

    assert calls
    _assert_standard_run(Path(result["report"]), root=tmp_path, command="universe_pti", scope="2021_05_28")
    assert Path(result["report"]).name == "universe_pti__report.html"


def test_premarket_defaults_to_standard_run_and_latest(monkeypatch, tmp_path: Path) -> None:
    calls: list[dict[str, object]] = []

    def fake_export_premarket_watchlist(**kwargs):
        calls.append(kwargs)
        return {"watchlist": kwargs["output"], "report": kwargs["report_output"]}

    monkeypatch.setattr("scripts.export_premarket_watchlist.export_premarket_watchlist", fake_export_premarket_watchlist)

    result = cli._export_phase0_premarket(config_path=tmp_path / "config.yaml")

    assert calls
    _assert_standard_run(Path(result["watchlist"]), root=tmp_path, command="premarket", scope="watchlist")
    assert Path(result["watchlist"]).name == "premarket__watchlist.csv"
    assert Path(result["report"]).name == "premarket__report.html"
    assert calls[0]["latest_report_output"] == tmp_path / "reports" / "latest" / "watchlist" / "index.html"


def test_account_bill_defaults_to_standard_run_dir(monkeypatch, tmp_path: Path) -> None:
    class Account:
        account_id = "demo"
        database_path = tmp_path / "account.sqlite"

    account = Account()
    calls: list[dict[str, object]] = []

    monkeypatch.setattr(cli, "load_config", lambda path: {"phase0": {}})
    monkeypatch.setattr(cli, "load_simulated_accounts", lambda cfg, root: [account])

    def fake_export_account_bill_html(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(cli, "export_account_bill_html", fake_export_account_bill_html)

    result = cli._export_brief_account_bill(config_path=tmp_path / "config.yaml", brief_date="2026-06-25")

    assert calls
    _assert_standard_run(Path(result["account_bill"]), root=tmp_path, command="brief_account_bill", scope="demo")
    assert Path(result["account_bill"]).name == "account_bill__report.html"
