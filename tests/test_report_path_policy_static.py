from __future__ import annotations

import ast
from pathlib import Path


ALLOWED_REPORT_ROOTS = {
    "archive",
    "database_health",
    "phase0",
    "runs",
    "strategy_admission",
    "strategy_governance",
}
LEGACY_COMPAT_REPORT_ROOTS = {
    "account_bill_today",
    "watchlist_today",
}

PATH_FILES = [
    Path("config.yaml"),
    Path("phase0"),
    Path("scripts"),
]


def _iter_string_literals(path: Path) -> list[str]:
    if path.suffix == ".py":
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        return [node.value for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str)]
    return path.read_text(encoding="utf-8").splitlines()


def _iter_policy_violations() -> list[tuple[str, str]]:
    repo = Path.cwd()
    files: list[Path] = []
    for item in PATH_FILES:
        target = repo / item
        if target.is_dir():
            files.extend(path for path in target.rglob("*.py") if "__pycache__" not in path.parts)
        else:
            files.append(target)

    violations: list[tuple[str, str]] = []
    for path in files:
        for literal in _iter_string_literals(path):
            index = literal.find("reports/")
            while index >= 0:
                suffix = literal[index + len("reports/") :]
                root = suffix.split("/", 1)[0].split('"', 1)[0].split("'", 1)[0].strip()
                if root and root not in ALLOWED_REPORT_ROOTS | LEGACY_COMPAT_REPORT_ROOTS:
                    violations.append((str(path.relative_to(repo)), literal.strip()))
                    break
                index = literal.find("reports/", index + 1)
    return violations


def test_code_defaults_use_allowed_report_root_categories() -> None:
    violations = _iter_policy_violations()
    assert violations == []
