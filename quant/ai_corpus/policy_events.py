"""Macro policy-event recognition from finance-flash headlines (rule + embedding).

Two-stage pipeline:
1. rule pre-filter: keyword dictionaries flag candidate policy events (召回)
2. embedding refine: oMLX semantic classification into 落地/预期/否定 and
   direction (loose/tight/neutral) (精度)

Recognizes both China (降准/降息/LPR/MLF) and US (FOMC/加息/降息/QE/缩表) events.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

# ── rule dictionaries (stage 1: recall) ────────────────────────────────

CN_LOOSE_KEYWORDS = [
    "降准", "降息", "下调存款准备金", "下调LPR", "下调MLF", "下调逆回购",
    "降LPR", "降MLF", "宽松", "放水", "降贷款利率", "下调利率",
]
CN_TIGHT_KEYWORDS = [
    "加息", "上调存款准备金", "上调LPR", "上调MLF", "上调逆回购", "收紧",
    "升准", "提准", "上调利率", "稳健中性", "去杠杆",
]
US_LOOSE_KEYWORDS = [
    "降息", "QE", "量化宽松", "降息25", "降息50", "降息75", "降息100",
    "缩表结束", "放水", "宽松",
]
US_TIGHT_KEYWORDS = [
    "加息", "加息25", "加息50", "加息75", "加息100", "缩表", "taper",
    "缩减购债", "收紧", "鹰派加息",
]
POLICY_ENTITY_KEYWORDS = [
    "美联储", "FOMC", "央行", "人民银行", "中国人民银行", "联储", "Fed",
    "鲍威尔", "联储主席", "货币政策", "存款准备金", "LPR", "MLF", "逆回购",
    "SLF", "公开市场",
]

# 排除词：其他国家的央行/货币当局，避免误召回
NON_CN_US_ENTITY_KEYWORDS = [
    "挪威", "乌干达", "越南", "乌克兰", "欧洲央行", "欧央行", "日本央行",
    "英国央行", "澳洲联储", "韩国央行", "印度央行", "瑞士央行", "加拿大央行",
    "俄罗斯央行", "巴西央行", "墨西哥央行",
]


@dataclass(frozen=True)
class PolicyEventCandidate:
    title: str
    published_at: str
    source: str
    rule_hit: str  # which rule dictionary matched


@dataclass(frozen=True)
class PolicyEvent:
    date: str
    market: str  # "CN" | "US"
    direction: str  # "loose" | "tight" | "neutral"
    event_type: str  # 降准/降息/加息/QE/缩表/LPR...
    is_confirmed: str  # "落地" | "预期" | "否定"
    magnitude: str  # "large" | "medium" | "small" | "unknown"
    title: str
    source: str
    confidence: float


def rule_prefilter(df: pd.DataFrame, text_col: str = "title") -> pd.DataFrame:
    """Stage 1: keep rows whose title/body hits any policy keyword (召回).

    Excludes foreign (non CN/US) central banks to avoid mis-recall.
    """
    if df.empty:
        return pd.DataFrame()
    text = df[text_col].astype(str)
    mask = text.apply(_hits_any_keyword) & ~text.apply(_is_non_cn_us)
    return df[mask].copy()


def _hits_any_keyword(text: str) -> bool:
    all_kw = (
        CN_LOOSE_KEYWORDS + CN_TIGHT_KEYWORDS + US_LOOSE_KEYWORDS
        + US_TIGHT_KEYWORDS + POLICY_ENTITY_KEYWORDS
    )
    return any(k in text for k in all_kw)


def _is_non_cn_us(text: str) -> bool:
    """True if the text is about a foreign (non CN/US) central bank."""
    return any(k in text for k in NON_CN_US_ENTITY_KEYWORDS)


def rule_direction(title: str) -> tuple[str, str, str]:
    """Return (market, direction, event_type) from rule dictionaries.

    market: CN/US; direction: loose/tight/neutral; event_type: human label.
    """
    # US first (FOMC/Fed keywords)
    if any(k in title for k in ["美联储", "FOMC", "联储", "Fed"]):
        if any(k in title for k in US_TIGHT_KEYWORDS):
            return "US", "tight", _us_tight_type(title)
        if any(k in title for k in US_LOOSE_KEYWORDS):
            return "US", "loose", _us_loose_type(title)
        return "US", "neutral", "美联储"
    # China
    if any(k in title for k in CN_TIGHT_KEYWORDS):
        return "CN", "tight", _cn_tight_type(title)
    if any(k in title for k in CN_LOOSE_KEYWORDS):
        return "CN", "loose", _cn_loose_type(title)
    # 央行开展逆回购 = 投放流动性 = 宽松；逆回购到期/回笼 = 收紧
    if "逆回购" in title and ("开展" in title or "投放" in title or "操作" in title) and "到期" not in title:
        return "CN", "loose", "逆回购投放"
    if "逆回购" in title and ("到期" in title or "回笼" in title):
        return "CN", "tight", "逆回购回笼"
    return "CN", "neutral", "政策"


def _cn_loose_type(title: str) -> str:
    if "降准" in title or "存款准备金" in title:
        return "降准"
    if "LPR" in title:
        return "LPR下调"
    if "MLF" in title:
        return "MLF下调"
    if "逆回购" in title:
        return "逆回购下调"
    return "降息"


def _cn_tight_type(title: str) -> str:
    if "升准" in title or "提准" in title or "存款准备金" in title:
        return "升准"
    if "加息" in title:
        return "加息"
    return "收紧"


def _us_loose_type(title: str) -> str:
    if "QE" in title or "量化宽松" in title:
        return "QE"
    return "降息"


def _us_tight_type(title: str) -> str:
    if "缩表" in title or "taper" in title.lower() or "缩减购债" in title:
        return "缩表"
    return "加息"


def refine_with_embedding(
    candidates: pd.DataFrame,
    linker,
    text_col: str = "title",
) -> pd.DataFrame:
    """Stage 2: use oMLX embeddings to classify 落地/预期/否定 and confidence.

    ``linker`` is an OmlxEmbeddingLinker exposing ``encode(list[str])``.
    Classification is nearest-prototype over a small set of anchor phrases.
    """
    if candidates.empty:
        return candidates.assign(is_confirmed="落地", confidence=0.5)

    anchors = {
        "落地": "央行宣布下调存款准备金率 决定 实施 落地 正式",
        "预期": "市场预期 有望 或 可能 预计 传闻 据悉",
        "否定": "否认 不会 暂不 辟谣 不降息 不加息",
    }
    anchor_texts = list(anchors.values())
    anchor_vecs = np.asarray(linker.encode(anchor_texts))
    texts = candidates[text_col].astype(str).tolist()
    doc_vecs = np.asarray(linker.encode(texts))

    # cosine similarity to each anchor
    norms_a = np.linalg.norm(anchor_vecs, axis=1)
    norms_d = np.linalg.norm(doc_vecs, axis=1)
    sims = (doc_vecs @ anchor_vecs.T) / (norms_d[:, None] * norms_a[None, :] + 1e-9)
    best_idx = np.argmax(sims, axis=1)
    labels = ["落地", "预期", "否定"]
    out = candidates.copy()
    out["is_confirmed"] = [labels[i] for i in best_idx]
    out["confidence"] = sims.max(axis=1)
    return out
