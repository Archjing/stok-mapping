from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _install_fake_acpx(tmp_path: Path) -> tuple[dict[str, str], Path]:
    log_path = tmp_path / "acpx.log"
    fake_acpx = tmp_path / "acpx"
    fake_acpx.write_text(
        """#!/usr/bin/env python3
import json
import os
import sys

with open(os.environ["ACP_LOG"], "a", encoding="utf-8") as handle:
    handle.write(json.dumps(sys.argv[1:], ensure_ascii=False) + "\\n")
""",
        encoding="utf-8",
    )
    fake_acpx.chmod(0o755)
    env = os.environ.copy()
    env["PATH"] = f"{tmp_path}:{env['PATH']}"
    env["ACP_LOG"] = str(log_path)
    return env, log_path


def _run_script(script: str, *args: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(ROOT / script), *args],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def _acpx_calls(log_path: Path) -> list[list[str]]:
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_cloe_wrappers_show_usage_without_calling_acpx(tmp_path: Path) -> None:
    env, log_path = _install_fake_acpx(tmp_path)

    for script in [
        "scripts/cloe_agent.sh",
        "scripts/cloe_premarket_agent.sh",
        "scripts/cloe_research_agent.sh",
        "scripts/cloe_risk_agent.sh",
    ]:
        result = _run_script(script, env=env)
        assert result.returncode == 2
        assert "Usage:" in result.stdout

    assert _acpx_calls(log_path) == []


def test_cloe_wrappers_preserve_default_sessions_and_ttl_behavior(tmp_path: Path) -> None:
    env, log_path = _install_fake_acpx(tmp_path)

    cases = [
        ("scripts/cloe_agent.sh", "cloe-bridge", False),
        ("scripts/cloe_premarket_agent.sh", "cloe-premarket", True),
        ("scripts/cloe_research_agent.sh", "cloe-research", False),
        ("scripts/cloe_risk_agent.sh", "cloe-risk", False),
    ]

    for script, expected_session, expects_ttl in cases:
        log_path.write_text("", encoding="utf-8")
        result = _run_script(script, "alpha", "beta", "gamma delta", env=env)
        calls = _acpx_calls(log_path)

        assert result.returncode == 0
        assert calls[0] == ["--cwd", str(ROOT), "openclaw", "sessions", "ensure", "--name", expected_session]
        assert calls[1][-4:] == ["openclaw", "-s", expected_session, "alpha beta gamma delta"]
        assert ("--ttl" in calls[1]) is expects_ttl
        if expects_ttl:
            assert calls[1][calls[1].index("--ttl") + 1] == "1800"
        assert calls[1][calls[1].index("--format") + 1] == "text"
        assert calls[1][calls[1].index("--timeout") + 1] == "600"


def test_role_specific_env_overrides_global_and_openclaw_fallback(tmp_path: Path) -> None:
    env, log_path = _install_fake_acpx(tmp_path)
    env.update(
        {
            "CLOE_RESEARCH_ACPX_SESSION": "role-session",
            "CLOE_ACPX_SESSION": "global-session",
            "OPENCLAW_ACPX_SESSION": "openclaw-session",
            "CLOE_ACPX_TIMEOUT": "777",
            "OPENCLAW_ACPX_FORMAT": "json",
        }
    )

    result = _run_script("scripts/cloe_research_agent.sh", "task", env=env)
    calls = _acpx_calls(log_path)

    assert result.returncode == 0
    assert calls[0] == ["--cwd", str(ROOT), "openclaw", "sessions", "ensure", "--name", "role-session"]
    assert calls[1][calls[1].index("--timeout") + 1] == "777"
    assert calls[1][calls[1].index("--format") + 1] == "json"
    assert calls[1][-4:] == ["openclaw", "-s", "role-session", "task"]


def test_premarket_ttl_uses_role_global_openclaw_fallback_order(tmp_path: Path) -> None:
    env, log_path = _install_fake_acpx(tmp_path)
    env.update(
        {
            "CLOE_PREMARKET_ACPX_TTL": "42",
            "CLOE_ACPX_TTL": "84",
            "OPENCLAW_ACPX_TTL": "168",
        }
    )

    result = _run_script("scripts/cloe_premarket_agent.sh", "task", env=env)
    assert result.returncode == 0
    call = _acpx_calls(log_path)[1]
    assert call[call.index("--ttl") + 1] == "42"

    log_path.write_text("", encoding="utf-8")
    env.pop("CLOE_PREMARKET_ACPX_TTL")
    result = _run_script("scripts/cloe_premarket_agent.sh", "task", env=env)
    assert result.returncode == 0
    call = _acpx_calls(log_path)[1]
    assert call[call.index("--ttl") + 1] == "84"

    log_path.write_text("", encoding="utf-8")
    env.pop("CLOE_ACPX_TTL")
    result = _run_script("scripts/cloe_premarket_agent.sh", "task", env=env)
    assert result.returncode == 0
    call = _acpx_calls(log_path)[1]
    assert call[call.index("--ttl") + 1] == "168"


def test_openclaw_compat_entrypoint_uses_cloe_agent_contract(tmp_path: Path) -> None:
    env, log_path = _install_fake_acpx(tmp_path)
    env["OPENCLAW_ACPX_SESSION"] = "compat-session"

    result = _run_script("scripts/openclaw_agent.sh", "compat", "task", env=env)
    calls = _acpx_calls(log_path)

    assert result.returncode == 0
    assert calls[0] == ["--cwd", str(ROOT), "openclaw", "sessions", "ensure", "--name", "compat-session"]
    assert calls[1][-4:] == ["openclaw", "-s", "compat-session", "compat task"]
