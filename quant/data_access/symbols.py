from __future__ import annotations

import re


_TUSHARE_TO_LOCAL = {"SH": "SH", "SZ": "SZ", "BJ": "BJ", "CSI": "CSI"}
_LOCAL_TO_TUSHARE = {value: key for key, value in _TUSHARE_TO_LOCAL.items()}


def from_tushare_symbol(value: object) -> str:
    raw = str(value or "").strip().upper()
    match = re.fullmatch(r"(\d{6})\.([A-Z]+)", raw)
    if match is None:
        return ""
    code, suffix = match.groups()
    prefix = _TUSHARE_TO_LOCAL.get(suffix)
    return f"{prefix}.{code}" if prefix else ""


def to_tushare_symbol(value: object) -> str:
    raw = str(value or "").strip().upper()
    match = re.fullmatch(r"([A-Z]+)\.(\d{6})", raw)
    if match is None:
        return ""
    prefix, code = match.groups()
    suffix = _LOCAL_TO_TUSHARE.get(prefix)
    return f"{code}.{suffix}" if suffix else ""


def normalize_etf_symbol(value: object) -> str:
    raw = str(value or "").strip().upper()
    local = raw if re.fullmatch(r"[A-Z]+\.\d{6}", raw) else from_tushare_symbol(raw)
    if not local:
        raise ValueError("ETF symbol must be exchange-qualified, for example SH.510300 or 510300.SH")
    if not re.fullmatch(r"(?:SH|SZ)\.\d{6}", local):
        raise ValueError("ETF symbol exchange must be SH or SZ")
    return local
