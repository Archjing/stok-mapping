from pathlib import Path

import pandas as pd

from quant.intelligence import tiingo_news_probe


def test_tiingo_news_probe_default_output_uses_configured_archive_category(monkeypatch, tmp_path: Path) -> None:
    (tmp_path / "config.yaml").write_text(
        """
quant:
  reporting:
    root_dir: local_reports
    categories:
      archive: archived
""",
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["tiingo_news_probe.py", "--days", "1", "--limit", "1"])
    monkeypatch.setattr(tiingo_news_probe, "fetch_tiingo_news", lambda **kwargs: pd.DataFrame())

    exit_code = tiingo_news_probe.main()

    assert exit_code == 0
    assert (tmp_path / "local_reports" / "archived" / "intelligence" / "tiingo_news_probe_report.md").exists()


def test_tiingo_news_probe_explicit_output_remains_project_relative(monkeypatch, tmp_path: Path) -> None:
    (tmp_path / "config.yaml").write_text("quant: {}\n", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["tiingo_news_probe.py", "--output", "custom/probe.md", "--days", "1", "--limit", "1"])
    monkeypatch.setattr(tiingo_news_probe, "fetch_tiingo_news", lambda **kwargs: pd.DataFrame())

    exit_code = tiingo_news_probe.main()

    assert exit_code == 0
    assert (tmp_path / "custom" / "probe.md").exists()
    assert not (tmp_path / "reports" / "archive" / "intelligence" / "custom" / "probe.md").exists()
