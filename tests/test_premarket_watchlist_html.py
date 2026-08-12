import pandas as pd

from quant.reporting.premarket_watchlist import _format_html


def test_watchlist_table_aligns_close_price_right_and_other_numeric_columns_center() -> None:
    watchlist = pd.DataFrame(
        [
            {
                "动作": "关注买入",
                "信号动作": "候选观察",
                "股票代码": "000001.SZ",
                "股票名称": "平安银行",
                "收盘价": "12.34",
                "当前权重": "0.00%",
                "目标权重": "5.00%",
                "权重变化": "5.00%",
                "持仓天数": "0",
                "动量分数": "1.2345",
                "当日排名": "1",
                "信号持有天数": "3",
                "成交价口径": "close",
                "最大成交参与率": "5.00%",
                "执行风险提示": "未发现明显执行阻碍，仍需开盘确认价格和成交量",
                "账户说明": "未进入模拟账户持仓，仅保留观察",
                "观察理由": "动量分数超过买入阈值",
            }
        ]
    )
    summary = {
        "strategy_display_name": "测试策略",
        "signal_date": "2026-06-29",
        "check_time": "2026-06-30 07:30",
        "watchlist_rows": 1,
        "account_summary_cards": [],
        "current_exposure": 0.0,
        "target_exposure": 0.05,
        "buy_or_add_rows": 1,
        "sell_or_reduce_rows": 0,
        "strategy_description": "测试说明",
        "position_source": "测试持仓",
        "account_snapshot_rows": "",
    }

    html = _format_html(watchlist, summary)

    assert '<html lang="zh-CN" data-theme="light">' in html
    assert '<link rel="stylesheet" href="style.css">' in html
    assert '<link rel="icon" href="data:image/svg+xml,' in html
    assert 'src="watchlist.js"' not in html
    assert "<style>" not in html
    assert 'id="themeToggle"' in html
    assert '<span class="icon" id="themeIcon">☀️</span>' in html
    assert "Belafonte Day" in html
    assert "Belafonte Night" in html
    assert 'id="backToTop"' in html
    assert "var STORAGE_KEY = 'belafonte-theme';" in html
    assert "localStorage.setItem(STORAGE_KEY, next);" in html
    assert "window.scrollTo({ top: 0, behavior: 'smooth' });" in html
    assert '<table class="watchlist-table">' in html
    assert '<td class="num-right">12.34</td>' in html
    assert '<td class="num-center">0.00%</td>' in html
    assert '<td class="num-center">1.2345</td>' in html
    assert '<td class="num-center">1</td>' in html
    assert '<td title="仍需开盘确认价格和成交量">未发现明显执行阻碍</td>' in html
    assert "持仓天数" in html
    assert "信号持有天数" in html
    assert "不是已成交记录，也不是自动下单指令" in html


def test_watchlist_static_assets_include_belafonte_theme_and_interactions() -> None:
    root = __import__("pathlib").Path(__file__).resolve().parents[1]
    css = (root / "quant" / "reporting" / "static" / "style.css").read_text(encoding="utf-8")

    assert "Based on macOS Terminal Themes by Jan T. Sott" in css
    assert "Belafonte Day" in css
    assert "Belafonte Night" in css
    assert 'font-family: "Microsoft YaHei", "微软雅黑", "PingFang SC", "Noto Sans SC", sans-serif;' in css
    assert "--amber:      #d08b30;" in css
    assert "--focus-text: #6f4515;" in css
    assert "--focus-row:  #f3ead6;" in css
    assert "[data-theme=\"dark\"]" in css
    dark_theme = css.split('[data-theme="dark"] {', 1)[1].split("}", 1)[0]
    assert "--text:       #b88f55;" in dark_theme
    assert "--text-dim:   #96754e;" in dark_theme
    assert "--text-muted: #6f5a43;" in dark_theme
    assert "--amber:      #eaa549;" in dark_theme
    assert "--focus-text: #d09a45;" in dark_theme
    assert "--focus-strong:#eaa549;" in dark_theme
    assert "--header-fg:  #d5ccba;" in dark_theme
    assert ".buy td  {" in css
    assert "color: var(--focus-text);" in css
    assert "font-weight: 800; color: var(--focus-strong);" not in css
    assert "@media (min-width: 1920px)" in css
    assert "@media (min-width: 2560px)" in css
    assert ".back-to-top.visible" in css
