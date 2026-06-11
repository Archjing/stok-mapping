# Stok Quant Research Plugin

Project-specific Codex plugin for Stok Mapping quant research workflows.

## Purpose

This plugin adapts the financial-services-agent pattern to this repository:

- data governance and scheduler health
- Tushare backfill operations
- factor diagnostics and PIT coverage review
- strategy admission and walk-forward validation
- daily brief operations
- investment strategy intelligence workflows

It does not replace the project CLI. The CLI remains the deterministic execution layer.

## Reused Local Skill Sources

The following loose skills under `/home/zj/workspace/skills` are useful references:

- `earnings-reviewer`
- `dcf-model`
- `comps-analysis`
- `tushare-data`
- `article-ingest`
- `wiki-ingest`
- `clean-content-fetch`
- `logseq`
- `zettelkasten-cn`
- `multi-search-engine`
- `mcp-adapter`

This plugin does not copy those skills verbatim. It wraps Stok Mapping specific workflows and points to local references where reuse is appropriate.

## Current Skills

- `data-governance`
- `strategy-admission`
- `factor-diagnostics`
- `tushare-backfill`
- `research-intelligence`
- `daily-brief-ops`

## Boundaries

- No paid market-data connector is bundled.
- No external MCP server is enabled by default.
- No runtime reports, logs, or SQLite state files should be committed as part of this plugin.
