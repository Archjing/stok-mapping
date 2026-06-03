from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import requests


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = PROJECT_ROOT / ".codex" / "claude_agent_config.json"
LOCAL_CONFIG = PROJECT_ROOT / ".codex" / "claude_agent.local.json"
DEFAULT_CLAUDE_SETTINGS = Path.home() / ".claude" / "settings.json"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def load_claude_settings_env(path: Path = DEFAULT_CLAUDE_SETTINGS) -> None:
    settings = load_json(path)
    env = settings.get("env", {})
    if not isinstance(env, dict):
        return
    for key, value in env.items():
        if key and value and key not in os.environ:
            os.environ[str(key)] = str(value)


def merged_config(config_path: Path) -> dict[str, Any]:
    config = load_json(config_path)
    local = load_json(LOCAL_CONFIG)
    for key, value in local.get("env", {}).items():
        if key and value and key not in os.environ:
            os.environ[str(key)] = str(value)
    config.update(local.get("overrides", {}))
    return config


def resolve_model(config: dict[str, Any]) -> str:
    model_env = str(config.get("model_env", "")).strip()
    if model_env:
        model = os.environ.get(model_env, "").strip()
        if model:
            return model
    return str(config["model"])


def read_project_file(relative_path: str, max_chars: int) -> str:
    path = (PROJECT_ROOT / relative_path).resolve()
    root = PROJECT_ROOT.resolve()
    if path != root and root not in path.parents:
        return f"## {relative_path}\n\n[skipped: outside project]\n"
    if not path.exists():
        return f"## {relative_path}\n\n[missing]\n"
    if not path.is_file():
        return f"## {relative_path}\n\n[skipped: not a file]\n"
    text = path.read_text(encoding="utf-8", errors="replace")
    clipped = text[:max_chars]
    suffix = "\n\n[truncated]\n" if len(text) > max_chars else ""
    return f"## {relative_path}\n\n```text\n{clipped}\n```{suffix}\n"


def build_prompt(config: dict[str, Any], task: str, include_files: list[str]) -> str:
    max_per_file = int(config.get("max_input_chars_per_file", 12000))
    remaining = int(config.get("max_total_input_chars", 36000))
    constraints = config.get(
        "prompt_constraints",
        [
            "输出语言：中文。",
            "只做研究辅助、风险提示、验证建议和待办整理。",
            "不输出买入、卖出、清仓、满仓等交易指令。",
            "不擅自改变策略逻辑或策略参数。",
            "若引用结论，注明来自哪个本地文件。",
        ],
    )
    sections = [
        "# Task",
        task.strip(),
        "",
        "# Constraints",
        *[f"- {item}" for item in constraints],
        "",
        "# Project Context",
    ]
    for relative_path in include_files:
        if remaining <= 0:
            sections.append("[context budget exhausted]")
            break
        chunk = read_project_file(relative_path, min(max_per_file, remaining))
        remaining -= len(chunk)
        sections.append(chunk)
    return "\n".join(sections)


def resolve_api_url(config: dict[str, Any]) -> str:
    base_url = os.environ.get("ANTHROPIC_BASE_URL", "").strip()
    if base_url:
        normalized = base_url.rstrip("/")
        if normalized.endswith("/v1/messages"):
            return normalized
        if normalized.endswith("/v1"):
            return f"{normalized}/messages"
        return f"{normalized}/v1/messages"
    return str(config.get("api_url", "https://api.anthropic.com/v1/messages"))


def resolve_auth_headers(config: dict[str, Any]) -> dict[str, str]:
    auth_token = os.environ.get("ANTHROPIC_AUTH_TOKEN", "").strip()
    if auth_token:
        return {"Authorization": f"Bearer {auth_token}"}

    api_key_env = str(config.get("api_key_env", "ANTHROPIC_API_KEY"))
    api_key = os.environ.get(api_key_env, "").strip()
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_AUTH_TOKEN is not set; set it as a system variable or in .env. "
            f"Fallback {api_key_env} is also not set."
        )
    return {"x-api-key": api_key}


def call_anthropic(config: dict[str, Any], prompt: str) -> str:
    payload = {
        "model": resolve_model(config),
        "max_tokens": int(config.get("max_tokens", 1600)),
        "temperature": float(config.get("temperature", 0.2)),
        "system": config.get("system_prompt", ""),
        "messages": [{"role": "user", "content": prompt}],
    }
    headers = {
        **resolve_auth_headers(config),
        "anthropic-version": str(config.get("anthropic_version", "2023-06-01")),
        "content-type": "application/json",
    }
    response = requests.post(
        resolve_api_url(config),
        headers=headers,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        timeout=int(config.get("timeout_seconds", 60)),
    )
    response.raise_for_status()
    data = response.json()
    blocks = data.get("content", [])
    return "\n".join(
        block.get("text", "")
        for block in blocks
        if isinstance(block, dict) and block.get("type") == "text"
    ).strip()


def write_output(path: Path, *, model: str, dry_run: bool, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    header = (
        "# Claude Agent Output\n\n"
        f"- generated_at: {datetime.now().isoformat(timespec='seconds')}\n"
        f"- model: {model}\n"
        f"- dry_run: {str(dry_run).lower()}\n\n"
    )
    path.write_text(header + body.rstrip() + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Claude as a bounded stok-mapping agent")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="Path to .codex Claude provider config")
    parser.add_argument(
        "--task",
        default=None,
        help="Task instruction sent to Claude",
    )
    parser.add_argument("--include", action="append", default=None, help="Project-relative context file")
    parser.add_argument("--output", default=None, help="Project-relative or absolute output markdown path")
    parser.add_argument("--dry-run", action="store_true", help="Write prompt preview without calling Anthropic API")
    args = parser.parse_args()

    load_dotenv(PROJECT_ROOT / ".env")
    load_claude_settings_env()
    config = merged_config(Path(args.config).resolve())
    task = args.task or str(
        config.get("default_task", "基于当前上下文生成摘要、风险提示、失效条件和下一步验证建议。")
    )
    include_files = args.include or list(config.get("include_files", []))
    prompt = build_prompt(config, task, include_files)
    output_raw = args.output or config.get("output_path", "reports/claude_agent_latest.md")
    output_path = Path(output_raw)
    if not output_path.is_absolute():
        output_path = PROJECT_ROOT / output_path

    if args.dry_run:
        write_output(output_path, model=resolve_model(config), dry_run=True, body="## Prompt Preview\n\n" + prompt)
        print(f"dry_run_output={output_path}")
        return 0

    response_text = call_anthropic(config, prompt)
    write_output(output_path, model=resolve_model(config), dry_run=False, body=response_text)
    print(f"agent_output={output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
