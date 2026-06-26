# Reports Directory Policy

`reports/` is primarily a local runtime output area. Routine generated reports
should not be committed.

Versioned report content is limited to curated governance archives that explain
strategy research decisions and keep enough evidence for later review:

- `reports/strategy_governance/<date>/<topic>/`

Default command outputs should use standard run directories:

- `reports/runs/<YYYY-MM-DD>/<timestamp>__<command>__<scope>/`

Latest mirrors and scratch outputs are local only:

- `reports/latest/`
- `reports/scratch/`
- `reports/archive/`
