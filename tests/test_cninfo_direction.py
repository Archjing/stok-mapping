"""Tests for cninfo earnings-forecast direction parsing."""
from __future__ import annotations

from quant.ai_corpus.providers.cninfo_direction import (
    announcement_pdf_url,
    classify_forecast_direction,
)


def test_pdf_url_derivation() -> None:
    url = ("http://www.cninfo.com.cn/new/disclosure/detail"
           "?stockCode=600703&announcementId=1207240896&orgId=gssh0600703&announcementTime=2020-01-11")
    assert announcement_pdf_url(url, "2020-01-11") == (
        "http://static.cninfo.com.cn/finalpage/2020-01-11/1207240896.PDF"
    )


def test_classify_title_explicit_labels() -> None:
    assert classify_forecast_direction("2024年年度业绩预增公告", "") == "预增"
    assert classify_forecast_direction("2024年年度业绩预减公告", "") == "预减"
    assert classify_forecast_direction("2024年年度业绩预亏公告", "") == "预亏"
    assert classify_forecast_direction("扭亏为盈公告", "") == "扭亏"


def test_classify_checked_checkbox() -> None:
    # 勾选框形式：√同向上升 才是有效证据，未选中的选项词不算
    head = "预计的经营业绩： 亏损   扭亏为盈   √同向上升  同向下降"
    assert classify_forecast_direction("2019年度业绩预告", head) == "预增"
    head2 = "预计的经营业绩： 亏损   扭亏为盈   同向上升  √同向下降"
    assert classify_forecast_direction("2019年度业绩预告", head2) == "预减"


def test_classify_percentage_phrases() -> None:
    assert classify_forecast_direction("", "净利润同比减少45%到55%") == "预减"
    assert classify_forecast_direction("", "净利润同比增加193%到213%") == "预增"


def test_classify_body_noise_does_not_mislead() -> None:
    # 正文里"集成电路业务全年继续亏损"不应把整体方向判成续亏
    head = "净利润与上年同期相比减少127,360.00万元到155,660.00万元，同比减少45%到55%。"
    assert classify_forecast_direction("", head) == "预减"


def test_classify_unknown() -> None:
    assert classify_forecast_direction("", "本公司业绩预告数据未经审计") == "未知"
