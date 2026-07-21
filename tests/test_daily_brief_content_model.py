from __future__ import annotations

from phase0.reporting.daily_brief import (
    DAILY_BRIEF_SECTION_ORDER,
    NO_ADMISSION_PASS_MESSAGE,
    DailyBriefDocument,
    DailyBriefMetadata,
    build_account_summary,
    build_empty_daily_brief_document,
)


def test_account_summary_uses_initial_cash_when_bill_is_missing() -> None:
    summary = build_account_summary(
        {},
        account_id="default",
        account_name="模拟账户",
        initial_cash=500_000.0,
        bill_confirmed=False,
    )

    assert summary.total_asset == 500_000.0
    assert summary.cash_asset == 500_000.0
    assert summary.stock_asset == 0.0
    assert summary.exposure == 0.0
    assert summary.current_return is None
    assert summary.current_return_display == "暂无"
    assert summary.bill_status == "unconfirmed_or_missing"
    assert [item["key"] for item in summary.span_items()] == [
        "total_asset",
        "cash_asset",
        "stock_asset",
        "exposure",
        "current_return",
    ]


def test_account_summary_uses_confirmed_bill_snapshot() -> None:
    summary = build_account_summary(
        {
            "account_id": "default",
            "brief_date": "2026-07-02",
            "total_asset": 1_050_000.0,
            "cash_asset": 250_000.0,
            "stock_asset": 800_000.0,
            "daily_return": 0.0123,
        },
        account_name="默认模拟账户",
        initial_cash=1_000_000.0,
        bill_confirmed=True,
    )

    assert summary.total_asset == 1_050_000.0
    assert summary.cash_asset == 250_000.0
    assert summary.stock_asset == 800_000.0
    assert round(summary.exposure, 6) == round(800_000.0 / 1_050_000.0, 6)
    assert summary.current_return == 0.0123
    assert summary.current_return_display == "1.23%"
    assert summary.bill_status == "confirmed"
    assert summary.bill_date == "2026-07-02"


def test_empty_daily_brief_document_has_required_sections_and_boundaries() -> None:
    document = build_empty_daily_brief_document(
        brief_date="2026-07-03",
        signal_date="2026-07-02",
        generated_at="2026-07-03T07:30:00",
        account_id="default",
        account_name="默认模拟账户",
        initial_cash=1_000_000.0,
    )
    payload = document.to_dict()

    assert [section["key"] for section in payload["sections"]] == DAILY_BRIEF_SECTION_ORDER
    assert payload["metadata"]["brief_date"] == "2026-07-03"
    assert payload["account_summary"]["spans"][4]["value"] == "暂无"
    assert payload["strategy_status"]["status"] == "research_only"
    assert payload["strategy_status"]["has_admission_pass"] is False
    assert NO_ADMISSION_PASS_MESSAGE in payload["strategy_status"]["summary"]
    assert "不构成投资建议" in payload["disclaimer"]


def test_custom_sections_keep_contract_order() -> None:
    account_summary = build_account_summary({}, initial_cash=1_000_000.0)
    document = DailyBriefDocument(
        metadata=DailyBriefMetadata(brief_date="2026-07-03"),
        account_summary=account_summary,
    )

    assert [section.key for section in document.ordered_sections()] == DAILY_BRIEF_SECTION_ORDER
