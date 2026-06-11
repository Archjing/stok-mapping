from pathlib import Path

from phase0.maintenance_orchestrator import _default_registry


def test_daily_brief_uses_cn_health_scope_by_default() -> None:
    specs = _default_registry(Path("config.yaml"))
    daily_brief = next(item for item in specs if item.name == "daily_brief")
    assert daily_brief.health_scope == "cn"
