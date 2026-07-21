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
    monkeypatch.setattr(module, "_summary_from_folds", lambda folds, governance, strategy_id, bill, daily, **kwargs: {})
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
    monkeypatch.setattr(module, "_summary_from_folds", lambda folds, governance, strategy_id, bill, daily, **kwargs: {})
    monkeypatch.setattr(module, "_gate_rows", lambda summary, gate_cfg: [("ok", True)])
    monkeypatch.setattr(module, "_write_report", lambda path, **kwargs: Path(path).write_text("report", encoding="utf-8"))

    result = module.export_execution_effectiveness_report(config_path=config_path, strategy_id="demo")

    assert Path(calls[0]["output"]) == tmp_path / "local_reports" / "phase_zero" / "live" / "bill.csv"
    assert Path(calls[0]["daily_output"]) == tmp_path / "local_reports" / "phase_zero" / "live" / "daily.csv"
    assert result["folds"] == tmp_path / "local_reports" / "phase_zero" / "live" / "folds.csv"
    assert result["report"] == tmp_path / "local_reports" / "phase_zero" / "live" / "report.md"


def test_summary_marks_account_execution_metrics_as_gate_source() -> None:
    folds = pd.DataFrame(
        [
            {
                "fold": 1,
                "valid_start": "2024-01-01",
                "valid_end": "2024-01-31",
                "annualized_return": 0.12,
                "sharpe": 1.1,
                "max_drawdown": -0.08,
                "win_rate": 0.55,
                "turnover_annual": 1.0,
            }
        ]
    )

    summary = module._summary_from_folds(
        folds,
        {"min_portfolio_fold_count": 1},
        strategy_id="demo",
        gate_source="account_daily_assets",
    )

    assert summary["metric_source"] == "account_daily_assets"
    assert summary["performance_metric_source"] == "account_execution"
    assert summary["account_annualized_return_mean"] == summary["annualized_return_mean"]
    assert summary["account_sharpe_mean"] == summary["sharpe_mean"]
    assert summary["research_annualized_return_mean"] is None


def test_gate_labels_use_account_metric_names_when_source_is_account_execution() -> None:
    groups = module._gate_groups(
        {
            "selected_candidate_eligible": True,
            "metric_source": "account_daily_assets",
            "annualized_return_mean": 0.12,
            "sharpe_mean": 1.1,
            "max_drawdown_mean": -0.08,
            "win_rate_mean": 0.55,
            "oos_return_decay_ratio": 0.1,
            "oos_fold_count": 1,
            "oos_annualized_return_mean": 0.10,
            "oos_sharpe_mean": 1.0,
            "positive_fold_ratio": 1.0,
            "negative_fold_count": 0,
            "min_fold_annualized_return": 0.12,
            "oos_positive_fold_ratio": 1.0,
        },
        {"annualized_return_min": 0.0, "sharpe_min": 0.5, "max_drawdown_min": -0.25, "win_rate_min": 0.45},
    )

    labels = [name for name, _ok in groups["base"]]

    assert any(label.startswith("account_annualized_return_mean >") for label in labels)
    assert any(label.startswith("account_sharpe_mean >") for label in labels)
    assert not any(label.startswith("annualized_return_mean >") for label in labels)


def test_report_documents_account_vs_research_metric_boundary(tmp_path: Path) -> None:
    report = tmp_path / "report.md"

    module._write_report(
        report,
        summary={
            "status": "ok",
            "selected_candidate_eligible": True,
            "metric_source": "account_daily_assets",
            "performance_metric_source": "account_execution",
            "annualized_return_mean": 0.12,
            "sharpe_mean": 1.1,
            "max_drawdown_mean": -0.08,
            "win_rate_mean": 0.55,
            "oos_return_decay_ratio": 0.1,
        },
        folds=pd.DataFrame(
            [
                {
                    "fold": 1,
                    "valid_start": "2024-01-01",
                    "valid_end": "2024-01-31",
                    "annualized_return": 0.12,
                    "sharpe": 1.1,
                    "max_drawdown": -0.08,
                    "win_rate": 0.55,
                    "trades": 1,
                    "final_account_assets": 101000.0,
                    "unfilled_orders": 0,
                }
            ]
        ),
        bill=pd.DataFrame(),
        daily=pd.DataFrame(),
        execution_cfg={"price_mode": "next_open"},
        live_cfg={"profile": "live", "gate_source": "account_daily_assets"},
        gate_cfg={"annualized_return_min": 0.0, "sharpe_min": 0.5, "max_drawdown_min": -0.25, "win_rate_min": 0.45},
    )

    text = report.read_text(encoding="utf-8")
    assert "账户级执行指标" in text
    assert "研究回测指标" in text
    assert "account_daily_assets" in text
