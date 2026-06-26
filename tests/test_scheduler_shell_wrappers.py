from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _copy_scheduler_scripts(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    scripts = project / "scripts"
    lib = scripts / "lib"
    lib.mkdir(parents=True)
    shutil.copy2(ROOT / "scripts" / "lib" / "project_env.sh", lib / "project_env.sh")
    shutil.copy2(ROOT / "scripts" / "run_project_scheduler.sh", scripts / "run_project_scheduler.sh")
    shutil.copy2(ROOT / "scripts" / "install_dev_cron.sh", scripts / "install_dev_cron.sh")
    (project / "config.yaml").write_text("phase0: {}\n", encoding="utf-8")
    return project


def _install_fake_python(project: Path) -> Path:
    log_path = project / "python_calls.jsonl"
    python_bin = project / ".venv" / "bin" / "python"
    python_bin.parent.mkdir(parents=True)
    python_bin.write_text(
        """#!/usr/bin/env python3
import json
import os
import sys

with open(os.environ["PYTHON_CALL_LOG"], "a", encoding="utf-8") as handle:
    handle.write(json.dumps({
        "argv": sys.argv[1:],
        "cwd": os.getcwd(),
        "env_flag": os.environ.get("STOK_TEST_ENV_FLAG", ""),
    }, ensure_ascii=False) + "\\n")
""",
        encoding="utf-8",
    )
    python_bin.chmod(0o755)
    return log_path


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_project_scheduler_wrapper_uses_shared_env_and_preserves_cli_calls(tmp_path: Path) -> None:
    project = _copy_scheduler_scripts(tmp_path)
    log_path = _install_fake_python(project)
    (project / ".env").write_text("STOK_TEST_ENV_FLAG=loaded_from_dotenv\n", encoding="utf-8")
    env = os.environ.copy()
    env["PYTHON_CALL_LOG"] = str(log_path)

    result = subprocess.run(
        [str(project / "scripts" / "run_project_scheduler.sh")],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    calls = _read_jsonl(log_path)
    assert result.returncode == 0
    assert (project / "logs").is_dir()
    assert [call["argv"] for call in calls] == [
        ["-m", "phase0.cli", "maintain", "status", "--config", str(project / "config.yaml")],
        ["-m", "phase0.cli", "maintain", "tick", "--config", str(project / "config.yaml")],
    ]
    assert {call["cwd"] for call in calls} == {str(project)}
    assert {call["env_flag"] for call in calls} == {"loaded_from_dotenv"}


def test_install_dev_cron_wrapper_uses_shared_env_and_preserves_cron_block(tmp_path: Path) -> None:
    project = _copy_scheduler_scripts(tmp_path)
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    crontab_store = tmp_path / "crontab.txt"
    crontab_log = tmp_path / "crontab_calls.jsonl"
    fake_crontab = fake_bin / "crontab"
    fake_crontab.write_text(
        """#!/usr/bin/env python3
import json
import os
import pathlib
import sys

store = pathlib.Path(os.environ["FAKE_CRONTAB_STORE"])
log = pathlib.Path(os.environ["FAKE_CRONTAB_LOG"])
args = sys.argv[1:]
with log.open("a", encoding="utf-8") as handle:
    handle.write(json.dumps(args, ensure_ascii=False) + "\\n")
if args == ["-l"]:
    if store.exists():
        sys.stdout.write(store.read_text(encoding="utf-8"))
        raise SystemExit(0)
    raise SystemExit(1)
if len(args) == 1:
    store.write_text(pathlib.Path(args[0]).read_text(encoding="utf-8"), encoding="utf-8")
    raise SystemExit(0)
raise SystemExit(2)
""",
        encoding="utf-8",
    )
    fake_crontab.chmod(0o755)
    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}:{env['PATH']}"
    env["FAKE_CRONTAB_STORE"] = str(crontab_store)
    env["FAKE_CRONTAB_LOG"] = str(crontab_log)

    result = subprocess.run(
        [str(project / "scripts" / "install_dev_cron.sh")],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    installed = crontab_store.read_text(encoding="utf-8")
    expected_line = f"* * * * * bash {project}/scripts/run_project_scheduler.sh >> {project}/logs/project_scheduler.log 2>&1"
    installed_lines = [line for line in installed.splitlines() if line.strip()]
    assert result.returncode == 0
    assert (project / "logs").is_dir()
    assert installed_lines == [
        "# stok-mapping project scheduler start",
        expected_line,
        "# stok-mapping project scheduler end",
    ]
    crontab_calls = _read_jsonl(crontab_log)
    assert expected_line in result.stdout
    assert crontab_calls[0] == ["-l"]
    assert len(crontab_calls[1]) == 1
    assert crontab_calls[2] == ["-l"]
