from __future__ import annotations

from decimal import Decimal
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from quant.reporting.daily_brief import (
    DAILY_BRIEF_SECTION_ORDER,
    NO_ADMISSION_PASS_MESSAGE,
    DailyBriefDocument,
    DailyBriefMetadata,
    build_account_summary,
    build_empty_daily_brief_document,
)


def _valid_confirmed_snapshot() -> dict[str, object]:
    return {
        "account_id": "default",
        "brief_date": "2026-07-02",
        "total_asset": 1_050_000.0,
        "cash_asset": 250_000.0,
        "stock_asset": 800_000.0,
    }


def test_unconfirmed_snapshot_ignores_invalid_asset_fields_and_uses_initial_cash() -> None:
    summary = build_account_summary(
        {"total_asset": float("nan"), "cash_asset": -1.0, "stock_asset": "not-a-number"},
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
    assert summary.current_return == pytest.approx(0.05)
    assert summary.current_return_display == "5.00%"
    assert summary.bill_status == "confirmed"
    assert summary.bill_date == "2026-07-02"


@pytest.mark.parametrize("field,value", [("total_asset", None), ("cash_asset", None), ("stock_asset", None)])
def test_confirmed_snapshot_rejects_incomplete_asset_fields(field: str, value: object) -> None:
    snapshot = _valid_confirmed_snapshot()
    snapshot[field] = value

    with pytest.raises(ValueError, match=field):
        build_account_summary(snapshot, bill_confirmed=True)


@pytest.mark.parametrize("field", ["total_asset", "cash_asset", "stock_asset"])
def test_confirmed_snapshot_rejects_pandas_missing_asset_fields(field: str) -> None:
    snapshot = _valid_confirmed_snapshot()
    snapshot[field] = pd.NA

    with pytest.raises(ValueError, match=field):
        build_account_summary(snapshot, bill_confirmed=True)


@pytest.mark.parametrize("field", ["total_asset", "cash_asset", "stock_asset"])
def test_confirmed_snapshot_rejects_missing_required_asset_fields(field: str) -> None:
    snapshot = _valid_confirmed_snapshot()
    snapshot.pop(field)

    with pytest.raises(ValueError, match=field):
        build_account_summary(snapshot, bill_confirmed=True)


@pytest.mark.parametrize("field", ["total_asset", "cash_asset", "stock_asset"])
@pytest.mark.parametrize("value", ["not-a-number", True])
def test_confirmed_snapshot_rejects_non_numeric_asset_fields(field: str, value: object) -> None:
    snapshot = _valid_confirmed_snapshot()
    snapshot[field] = value

    with pytest.raises(ValueError, match=field):
        build_account_summary(snapshot, bill_confirmed=True)


@pytest.mark.parametrize("field", ["total_asset", "cash_asset", "stock_asset"])
@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf"), -1.0])
def test_confirmed_snapshot_rejects_non_finite_or_negative_asset_fields(field: str, value: float) -> None:
    snapshot = _valid_confirmed_snapshot()
    snapshot[field] = value

    with pytest.raises(ValueError, match=field):
        build_account_summary(snapshot, bill_confirmed=True)


def test_confirmed_snapshot_rejects_inconsistent_asset_fields() -> None:
    snapshot = _valid_confirmed_snapshot()
    snapshot.update(total_asset=10.00, cash_asset=4.00, stock_asset=5.00)

    with pytest.raises(ValueError, match="inconsistent") as exc_info:
        build_account_summary(snapshot, bill_confirmed=True)

    message = str(exc_info.value)
    for text in ("total_asset=10.0", "cash_asset=4.0", "stock_asset=5.0", "difference=1.0"):
        assert text in message


@pytest.mark.parametrize("value", [Decimal("1e1000000"), "1e1000000"])
def test_confirmed_snapshot_rejects_extreme_total_asset_with_diagnostic_value_error(value: object) -> None:
    snapshot = _valid_confirmed_snapshot()
    snapshot.update(total_asset=value, cash_asset=0.0, stock_asset=0.0)

    with pytest.raises(ValueError, match="total_asset"):
        build_account_summary(snapshot, bill_confirmed=True)


def test_confirmed_snapshot_rejects_nonzero_decimal_assets_that_underflow_to_float_zero() -> None:
    snapshot = _valid_confirmed_snapshot()
    snapshot.update(
        total_asset=Decimal("2e-4000"),
        cash_asset=Decimal("1e-4000"),
        stock_asset=Decimal("1e-4000"),
    )

    with pytest.raises(ValueError) as exc_info:
        build_account_summary(snapshot, bill_confirmed=True)

    assert "total_asset=2E-4000" in str(exc_info.value)


def test_confirmed_snapshot_rejects_decimal_assets_that_overflow_float_conversion() -> None:
    snapshot = _valid_confirmed_snapshot()
    snapshot.update(
        total_asset=Decimal("2e4000"),
        cash_asset=Decimal("1e4000"),
        stock_asset=Decimal("1e4000"),
    )

    with pytest.raises(ValueError) as exc_info:
        build_account_summary(snapshot, bill_confirmed=True)

    assert "total_asset=2E+4000" in str(exc_info.value)


def test_confirmed_snapshot_accepts_asset_fields_consistent_within_one_cent() -> None:
    snapshot = _valid_confirmed_snapshot()
    snapshot.update(total_asset=1.01, cash_asset=0.5, stock_asset=0.5)

    summary = build_account_summary(snapshot, bill_confirmed=True)

    assert summary.total_asset == pytest.approx(1.01)


def test_confirmed_snapshot_with_zero_initial_cash_has_no_current_return() -> None:
    summary = build_account_summary(
        {"total_asset": 0.0, "cash_asset": 0.0, "stock_asset": 0.0},
        initial_cash=0.0,
        bill_confirmed=True,
    )

    assert summary.current_return is None


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


def test_missing_account_summary_section_is_not_available() -> None:
    document = DailyBriefDocument(metadata=DailyBriefMetadata(brief_date="2026-07-03"))

    account_summary = next(section for section in document.ordered_sections() if section.key == "account_summary")

    assert account_summary.status == "not_available"
    assert account_summary.payload == {}


def test_reporting_package_import_does_not_require_jinja2() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "\n".join(
                [
                    "import sys",
                    "sys.modules['jinja2'] = None",
                    "import quant.reporting as reporting",
                    "assert reporting.DailyBriefDocument.__name__ == 'DailyBriefDocument'",
                ]
            ),
        ],
        cwd=Path(__file__).resolve().parent.parent,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
