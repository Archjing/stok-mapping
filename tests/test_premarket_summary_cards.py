from phase0.reporting.premarket_watchlist import _account_summary_cards


def test_account_summary_cards_include_requested_account_metrics() -> None:
    cards = _account_summary_cards(
        {
            "total_asset": 1_023_456.789,
            "cash_asset": 234_567.891,
            "stock_asset": 788_888.898,
            "target_exposure": 0.771,
            "daily_return": -0.0123,
        }
    )

    assert cards == [
        ("总资产（元）", "1,023,456.79"),
        ("可用资金（元）", "234,567.89"),
        ("持仓市值（元）", "788,888.90"),
        ("当前仓位（%）", "77.10%"),
        ("当前收益率（%）", "-1.23%"),
    ]


def test_account_summary_cards_keep_requested_spans_without_confirmed_account() -> None:
    cards = _account_summary_cards({}, initial_cash=1_000_000)

    assert cards == [
        ("总资产（元）", "1,000,000.00"),
        ("可用资金（元）", "1,000,000.00"),
        ("持仓市值（元）", "0.00"),
        ("当前仓位（%）", "0.00%"),
        ("当前收益率（%）", "暂无"),
    ]
