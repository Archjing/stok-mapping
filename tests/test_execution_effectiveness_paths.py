from pathlib import Path

import pandas as pd

from phase0.reporting import execution_effectiveness as module


def test_explicit_fold_and_report_outputs_remain_project_relative(monkeypatch, tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
phase0:
  reporting:
    root_dir: reports
    categories:
      phase0: phase0
      runs: runs
  walk_forward: {}
  execution: {}
  live_execution_backtest:
    default_profile: live
    profiles:
      live:
        name: Live
        walk_forward: {}
        execution: {}
""",
        encoding="utf-8",
    )
    calls = []

    def fake_export_strategy_bill(**kwargs):
        calls.append(kwargs)
        bill = Path(kwargs["output"])
        daily = Path(kwargs["daily_output"])
        preview = Path(kwargs["preview_output"])
        bill.parent.mkdir(parents=True, exist_ok=True)
        daily.parent.mkdir(parents=True, exist_ok=True)
        preview.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame({"策略ID": ["demo"], "fold": [1], "交易日期": ["2026-01-02"]}).to_csv(bill, index=False)
        pd.DataFrame({"strategy_id": ["demo"], "fold": [1], "date": ["2026-01-02"], "daily_return": [0.01]}).to_csv(
            daily,
            index=False,
        )
        preview.write_text("preview", encoding="utf-8")
        return {"bill": bill, "daily": daily, "preview": preview}

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(module, "_default_report_strategy_id", lambda config: "demo")
    monkeypatch.setattr(module, "execution_settings", lambda config: {})
    monkeypatch.setattr(module, "export_strategy_bill", fake_export_strategy_bill)
    monkeypatch.setattr(module, "_fold_metrics", lambda daily, bill, strategy_id: pd.DataFrame({"fold": [1], "daily_return": [0.01]}))
    monkeypatch.setattr(module, "_summary_from_folds", lambda folds, governance, strategy_id, bill, daily: {})
    monkeypatch.setattr(module, "_gate_rows", lambda summary, gate_cfg: [("ok", True)])
    monkeypatch.setattr(module, "_write_report", lambda path, **kwargs: Path(path).write_text("report", encoding="utf-8"))

    result = module.export_execution_effectiveness_report(
        config_path=config_path,
        strategy_id="demo",
        fold_output="custom/folds.csv",
        report_output="custom/report.md",
    )

    assert calls
    assert result["folds"] == tmp_path / "custom" / "folds.csv"
    assert result["report"] == tmp_path / "custom" / "report.md"
    assert not (tmp_path / "reports" / "phase0" / "custom" / "folds.csv").exists()
    assert not (tmp_path / "reports" / "phase0" / "custom" / "report.md").exists()


def test_configured_execution_outputs_resolve_under_report_root(monkeypatch, tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
phase0:
  reporting:
    root_dir: local_reports
    categories:
      phase0: phase_zero
      runs: run_outputs
  walk_forward: {}
  execution: {}
  live_execution_backtest:
    default_profile: live
    bill_output: phase0/live/bill.csv
    daily_output: phase0/live/daily.csv
    preview_output: phase0/live/preview.html
    fold_output: phase0/live/folds.csv
    report_output: phase0/live/report.md
    profiles:
      live:
        name: Live
        walk_forward: {}
        execution: {}
""",
        encoding="utf-8",
    )
    calls = []

    def fake_export_strategy_bill(**kwargs):
        calls.append(kwargs)
        bill = Path(kwargs["output"])
        daily = Path(kwargs["daily_output"])
        preview = Path(kwargs["preview_output"])
        bill.parent.mkdir(parents=True, exist_ok=True)
        daily.parent.mkdir(parents=True, exist_ok=True)
        preview.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame({"策略ID": ["demo"], "fold": [1], "交易日期": ["2026-01-02"]}).to_csv(bill, index=False)
        pd.DataFrame({"strategy_id": ["demo"], "fold": [1], "date": ["2026-01-02"], "daily_return": [0.01]}).to_csv(
            daily,
            index=False,
        )
        preview.write_text("preview", encoding="utf-8")
        return {"bill": bill, "daily": daily, "preview": preview}

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(module, "_default_report_strategy_id", lambda config: "demo")
    monkeypatch.setattr(module, "execution_settings", lambda config: {})
    monkeypatch.setattr(module, "export_strategy_bill", fake_export_strategy_bill)
    monkeypatch.setattr(module, "_fold_metrics", lambda daily, bill, strategy_id: pd.DataFrame({"fold": [1], "daily_return": [0.01]}))
    monkeypatch.setattr(module, "_summary_from_folds", lambda folds, governance, strategy_id, bill, daily: {})
    monkeypatch.setattr(module, "_gate_rows", lambda summary, gate_cfg: [("ok", True)])
    monkeypatch.setattr(module, "_write_report", lambda path, **kwargs: Path(path).write_text("report", encoding="utf-8"))

    result = module.export_execution_effectiveness_report(config_path=config_path, strategy_id="demo")

    assert Path(calls[0]["output"]) == tmp_path / "local_reports" / "phase_zero" / "live" / "bill.csv"
    assert Path(calls[0]["daily_output"]) == tmp_path / "local_reports" / "phase_zero" / "live" / "daily.csv"
    assert result["folds"] == tmp_path / "local_reports" / "phase_zero" / "live" / "folds.csv"
    assert result["report"] == tmp_path / "local_reports" / "phase_zero" / "live" / "report.md"
