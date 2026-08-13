"""Centralized project paths, derived from a single environment variable.

All database and data paths in the project resolve from ``STOK_MAPPING_ROOT``
(the project root directory).  Each path can also be overridden individually,
which the a-share-deep-analysis skill uses to point at the project without
hardcoding locations.

Environment variables:
- ``STOK_MAPPING_ROOT``: project root (default: the repo root derived from this
  file's location).  All paths below default to ``{root}/data/...``.
- Individual overrides: ``STOK_MARKET_DB``, ``STOK_CORPUS_DB``,
  ``STOK_MACRO_DB``, ``STOK_ETF_DB``, ``STOK_POLICY_EVENTS_CSV``.
"""
from __future__ import annotations

import os
from pathlib import Path

# Default project root = the repository root (two levels up from this file:
# quant/paths.py -> repo root).
_DEFAULT_ROOT = Path(__file__).resolve().parent.parent


def project_root() -> Path:
    raw = os.environ.get("STOK_MAPPING_ROOT", "")
    return Path(raw).expanduser() if raw else _DEFAULT_ROOT


def _resolve(env_name: str, relative: str) -> Path:
    override = os.environ.get(env_name, "")
    if override:
        return Path(override).expanduser()
    return project_root() / relative


def market_db() -> Path:
    """A-share market history (market_daily_bars / market_index_bars / ...)."""
    return _resolve("STOK_MARKET_DB", "data/a_share_history.sqlite")


def corpus_db() -> Path:
    """AI corpus documents (ai_corpus_documents)."""
    return _resolve("STOK_CORPUS_DB", "data/ai_corpus/ai_corpus.sqlite")


def macro_db() -> Path:
    """China/US macro series (macro_series)."""
    return _resolve("STOK_MACRO_DB", "data/macro_history.sqlite")


def etf_db() -> Path:
    """ETF history (market_etf_daily_bars)."""
    return _resolve("STOK_ETF_DB", "data/etf_history.sqlite")


def policy_events_csv() -> Path:
    """Structured macro policy events (date/direction/magnitude)."""
    return _resolve("STOK_POLICY_EVENTS_CSV", "data/macro_policy_events.csv")
