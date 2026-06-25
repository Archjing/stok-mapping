# Missing Core Member Audit

Generated at: 2026-06-25T12:47:36

## Scope

- Top symbols audited: `30`
- Fold-symbol rows audited: `31`
- Missing days represented by audited rows: `2630`
- Sum of missing benchmark weight over audited rows: `12.8696`
- Input reason: `missing_from_pit_panel` from strategy core reachability diagnostic.
- This is a read-only data coverage audit. It does not alter universe construction or strategy admission.

## Symbol Summary

| symbol | name | industry | folds | days | avg_rank | avg_weight | classification |
| --- | --- | --- | --- | --- | --- | --- | --- |
| SH.600000 | 浦发银行 | 银行 | 3 | 725 | 52.44 | 0.4919% | beyond_walk_forward_limit,ranked_out_or_balanced_out_of_pit_universe |
| SH.600016 | 民生银行 | 银行 | 2 | 484 | 49.88 | 0.4939% | beyond_walk_forward_limit,ranked_out_or_balanced_out_of_pit_universe |
| SH.600837 |  |  | 2 | 295 | 48.39 | 0.4975% | beyond_walk_forward_limit,universe_member_but_panel_missing |
| SH.601229 | 上海银行 | 银行 | 3 | 309 | 56.24 | 0.4525% | beyond_walk_forward_limit |
| SH.601816 | 京沪高铁 | 铁路 | 1 | 243 | 47.79 | 0.5271% | beyond_walk_forward_limit |
| SH.601169 | 北京银行 | 银行 | 2 | 182 | 61.67 | 0.4368% | beyond_walk_forward_limit,ranked_out_or_balanced_out_of_pit_universe |
| SH.600089 | 特变电工 | 电气设备 | 1 | 115 | 51.25 | 0.4881% | beyond_walk_forward_limit |
| SH.601728 | 中国电信 | 电信运营 | 1 | 58 | 60.97 | 0.4225% | beyond_walk_forward_limit |
| SZ.002028 | 思源电气 | 电气设备 | 1 | 36 | 48.64 | 0.5074% | beyond_walk_forward_limit |
| SH.600104 | 上汽集团 | 汽车整车 | 1 | 41 | 70.98 | 0.3976% | beyond_walk_forward_limit |
| SH.600900 | 长江电力 | 水力发电 | 2 | 11 | 10.30 | 1.3323% | universe_member_but_panel_missing |
| SH.600745 | *ST闻泰 | 半导体 | 1 | 19 | 60.11 | 0.4397% | filtered_out_before_universe_selection |
| SH.601766 | 中国中车 | 运输设备 | 1 | 23 | 72.00 | 0.3542% | beyond_walk_forward_limit |
| SH.601009 | 南京银行 | 银行 | 1 | 20 | 70.00 | 0.4027% | ranked_out_or_balanced_out_of_pit_universe |
| SH.688041 | 海光信息 | 半导体 | 1 | 10 | 30.00 | 0.6614% | universe_member_but_panel_missing |
| SH.600030 | 中信证券 | 证券 | 1 | 6 | 15.00 | 1.0202% | universe_member_but_panel_missing |
| SH.601088 | 中国神华 | 煤炭开采 | 1 | 10 | 36.00 | 0.5758% | universe_member_but_panel_missing |
| SH.688981 | 中芯国际 | 半导体 | 1 | 6 | 21.00 | 0.9513% | universe_member_but_panel_missing |
| SH.600150 | 中国船舶 | 船舶 | 1 | 10 | 59.00 | 0.4659% | universe_member_but_panel_missing |
| SH.603019 | 中科曙光 | IT设备 | 1 | 10 | 52.80 | 0.4620% | universe_member_but_panel_missing |
| SZ.002142 | 宁波银行 | 银行 | 1 | 6 | 29.17 | 0.7136% | universe_member_but_panel_missing |
| SH.688012 | DR中微公 | 半导体 | 1 | 9 | 49.00 | 0.4705% | universe_member_but_panel_missing |
| SH.601211 | 国泰海通 | 证券 | 1 | 2 | 71.00 | 0.4033% | universe_member_but_panel_missing |

## Classification Counts

| classification | fold_symbol_rows | missing_days | missing_weight |
| --- | --- | --- | --- |
| beyond_walk_forward_limit | 14 | 1897 | 9.2103 |
| universe_member_but_panel_missing | 12 | 134 | 0.8236 |
| ranked_out_or_balanced_out_of_pit_universe | 4 | 580 | 2.7521 |
| filtered_out_before_universe_selection | 1 | 19 | 0.0835 |

## Fold Classification Weights

| fold | classification | missing_days | missing_weight |
| --- | --- | --- | --- |
| 1 | universe_member_but_panel_missing | 22 | 0.2181 |
| 1 | beyond_walk_forward_limit | 21 | 0.0948 |
| 1 | filtered_out_before_universe_selection | 19 | 0.0835 |
| 2 | beyond_walk_forward_limit | 810 | 3.8728 |
| 2 | universe_member_but_panel_missing | 1 | 0.0152 |
| 3 | ranked_out_or_balanced_out_of_pit_universe | 560 | 2.6715 |
| 3 | beyond_walk_forward_limit | 282 | 1.3724 |
| 4 | beyond_walk_forward_limit | 381 | 1.9481 |
| 4 | universe_member_but_panel_missing | 66 | 0.3210 |
| 5 | beyond_walk_forward_limit | 403 | 1.9222 |
| 5 | universe_member_but_panel_missing | 45 | 0.2693 |
| 5 | ranked_out_or_balanced_out_of_pit_universe | 20 | 0.0805 |
