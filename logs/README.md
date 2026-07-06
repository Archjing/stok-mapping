# Logs Directory Policy

`logs/` stores machine runtime logs and scheduler state only.

Use this directory for:

- pipeline stdout/stderr logs such as `daily_brief_pipeline.log`;
- scheduler state and last-run stamps under `logs/scheduler/`;
- maintenance task logs under `logs/maintenance/`;
- lock files and operational traces needed to debug running jobs.

Do not store human-curated session archives, planning memories, or conversation
summaries here. Those belong under `memory/session_archive/`.

Do not store generated business reports here. Markdown/HTML/CSV report artifacts
belong under `reports/`.
