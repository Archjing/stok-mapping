from __future__ import annotations

import re
from typing import Any

import pandas as pd


def safe_identifier(value: str) -> str:
    if not value or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        raise ValueError(f"Unsafe SQL identifier: {value}")
    return value


def to_sql_value(value: Any) -> Any:
    if pd.isna(value):
        return None
    return value
