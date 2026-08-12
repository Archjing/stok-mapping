# Phase0 to Quant Compatibility Boundaries

`quant` is the application namespace. The following `phase0` strings remain
because they identify existing persisted artifacts rather than Python modules.

| Legacy identifier | Policy |
| --- | --- |
| `reports/phase0/` | Keep readable and writable until a separate artifact migration is approved. |
| `reports/phase0_*` | Keep existing filenames stable. New report families may use neutral names. |
| `data/simulated_trading/phase0_daily_account_ledger.csv` | Keep as configured persisted account state. |
| `data/simulated_trading/phase0_daily_brief_ledger.csv` | Keep as configured persisted brief state. |
| SQLite schemas and rows containing `phase0` | Do not rewrite in the namespace migration. |
| archived documents and Git history | Do not rewrite. |

## Python namespace policy

Only the following `phase0` Python modules are retained during the
compatibility window:

| Module | Responsibility |
| --- | --- |
| `phase0/__init__.py` | Deprecated compatibility-package marker only. |
| `phase0/cli.py` | Thin forwarder to `quant.cli.main`; emits a deprecation warning. |
| `phase0/__main__.py` | Optional forwarding support for `python -m phase0`. |

Importing any other `phase0.*` domain module (for example
`phase0.walk_forward`) fails with `ModuleNotFoundError`. A second supported
domain namespace would split module-level state, monkeypatch targets, caches,
and class identities.

## Configuration policy

- `config.yaml` uses the `quant:` root key.
- The loader accepts a legacy `phase0:` root with a `DeprecationWarning`.
- If both `quant:` and `phase0:` appear, startup fails rather than guessing.

## Scheduler persisted-command policy

Historical `maintenance_runs.command_json` and `maintenance_shards.command_json`
rows are audit records and are never rewritten. When the scheduler resumes a
persisted command that still names `phase0.cli`, the executed command is
normalized to `quant.cli` at the execution boundary
(`quant.maintenance_orchestrator._effective_maintenance_command`) and the log
records a `maintenance_command_normalized` line with both the original and the
effective command.

## Runtime cache policy

Runtime caches are disposable. The namespace migration bumps the cache-key
version to `quant-v1`; old cache files remain on disk but are ignored. The
migration does not delete user-owned cache files automatically.

## Removal criteria

The temporary `phase0.cli` forwarder, `stok-phase0` console alias, and the
legacy config-root fallback are governed by a separate cleanup release after a
30-day observation window (see the migration plan, Task 12). Removal requires:

- no non-test invocation of `python -m phase0.cli` during the final 10
  A-share trading days of the observation window;
- no enabled scheduler registry row that invokes `phase0.cli`;
- no persisted shard that depends on an unhandled legacy CLI command.
