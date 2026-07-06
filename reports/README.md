# Reports Directory Policy

`reports/` is a local report workspace with a deliberately small root layout.
Do not add new top-level report directories.

This directory is for program outputs only: research reports, audit reports,
HTML dashboards, CSV exports, and curated report archives. Human session memory
belongs in `memory/`; machine runtime logs belong in `logs/`.

Allowed root entries:

- `archive/` - legacy reports and manually preserved historical artifacts.
- `runs/` - standard command outputs, using
  `runs/<YYYY-MM-DD>/<timestamp>__<command>__<scope>/`.
- `database_health/` - database maintenance and data-health reports.
- `strategy_admission/` - strategy admission runs and diagnostics.
- `phase0/` - Phase 0 research, universe, and effectiveness artifacts.
- `strategy_governance/` - curated research governance archives.
- `README.md` - this policy.

Generated report files are local-only and should not be committed to the origin
repository. The root category directories are kept with `.gitkeep` placeholders
so `main` shows the intended structure without uploading generated artifacts.

Other repository copies may force-add their own reports if they intentionally
use a different tracking policy. This repository keeps report contents out of
normal version control.

Do not store session archives under `reports/**/session_archive/`. Use
`memory/session_archive/` instead, with a topic subdirectory when useful.

When older root-level reports must be retained locally, move them into one of
the allowed category directories instead of leaving them directly under
`reports/`.
