# Memory Directory Policy

`memory/` stores human-curated project memory: session summaries, decisions,
architecture notes, investigation conclusions, and historical planning snapshots
that should remain readable after logs and generated reports rotate.

Use this directory for:

- `session_archive/` - incremental session archives and conversation summaries.
- `session_archive/strategy_governance/` - strategy R&D Harness session memory.
- `session_archive/general/` - general engineering, operations, and research session memory.
- `development_plan_history/` - historical development-plan snapshots kept for context.

Do not put machine runtime logs here. Scheduler output, command stdout/stderr,
pipeline logs, lock files, and state stamps belong under `logs/`.

Do not put report artifacts here. Backtest reports, admission reports, HTML
dashboards, CSV exports, and generated Markdown reports belong under `reports/`.

Before context compression or long task handoff, write only the durable summary
needed for future recovery: new standards, key decisions, commands, changed
files, generated artifacts, verification results, unresolved risks, and next
steps. Avoid pasting raw terminal output unless it is itself the evidence.
