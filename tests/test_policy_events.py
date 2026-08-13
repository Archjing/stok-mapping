"""Tests for the macro policy-event recognition module."""
from __future__ import annotations

import pandas as pd

from quant.ai_corpus.policy_events import (
    rule_direction,
    rule_prefilter,
)


def _frame(titles: list[str]) -> pd.DataFrame:
    return pd.DataFrame({"title": titles})


def test_rule_prefilter_recalls_policy_events() -> None:
    df = _frame([
        "央行宣布下调存款准备金率0.5个百分点",
        "某公司发布年报",
        "美联储加息25个基点",
        "今日天气晴",
        "MLF利率下调",
    ])
    out = rule_prefilter(df)
    assert len(out) == 3  # 年报/天气 被排除


def test_rule_direction_china_loose() -> None:
    m, d, t = rule_direction("央行宣布下调存款准备金率0.5个百分点")
    assert (m, d, t) == ("CN", "loose", "降准")


def test_rule_direction_china_lpr() -> None:
    m, d, t = rule_direction("央行下调LPR 1年期10个基点")
    assert (m, d, t) == ("CN", "loose", "LPR下调")


def test_rule_direction_us_tight() -> None:
    m, d, t = rule_direction("美联储宣布加息50个基点")
    assert (m, d, t) == ("US", "tight", "加息")


def test_rule_direction_us_qe() -> None:
    m, d, t = rule_direction("美联储宣布新一轮量化宽松QE")
    assert (m, d, t) == ("US", "loose", "QE")


def test_rule_direction_neutral() -> None:
    m, d, t = rule_direction("央行发布货币政策执行报告")
    assert (m, d) == ("CN", "neutral")
