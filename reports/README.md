# Reports Directory Policy

`reports/` is a local report workspace with a deliberately small root layout.
Do not add new top-level report directories.

Allowed root entries:

- `archive/` - legacy reports and manually preserved historical artifacts.
- `runs/` - standard command outputs, using
  `runs/<YYYY-MM-DD>/<timestamp>__<command>__<scope>/`.
- `database_health/` - database maintenance and data-health reports.
- `strategy_admission/` - strategy admission runs and diagnostics.
- `phase0/` - Phase 0 research, universe, and effectiveness artifacts.
- `strategy_governance/` - curated research governance archives.
- `README.md` - this policy.

Routine generated files are local-only and should not be committed. The root
category directories are kept with `.gitkeep` placeholders so `main` shows the
intended structure without uploading generated artifacts.

Versioned report content is limited to curated governance archives that explain
strategy research decisions and keep enough evidence for later review:

- `strategy_governance/<date>/<topic>/`

When older root-level reports must be retained locally, move them into one of
the allowed category directories instead of leaving them directly under
`reports/`.
