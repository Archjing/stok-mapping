# Strategy R&D Harness 20260625

This directory keeps branch-specific research assets visible from `main`
without mixing generated artifacts into the project root.

## Contents

- `configs/`: dated configuration snapshots used during the 2026-06-25 to
  2026-06-26 strategy R&D Harness iterations.

## Version-Control Boundary

Tracked here:

- small config snapshots
- experiment notes and manifests
- scripts that are intentionally reusable

Ignored locally:

- `outputs/`
- `logs/`
- `data/`
- SQLite files

The config files under `configs/` are preserved as research snapshots. The
project CLI historically treats the config file parent as the project root for
some commands, so use these snapshots for review and controlled reruns only.
For routine runs, copy the intended snapshot to the repository root or create a
root-level config wrapper in a dedicated experiment branch.
