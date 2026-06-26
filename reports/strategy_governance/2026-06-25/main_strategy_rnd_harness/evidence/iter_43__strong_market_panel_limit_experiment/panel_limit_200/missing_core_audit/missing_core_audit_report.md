# Missing Core Member Audit

Generated at: 2026-06-25T12:44:43

## Scope

- Top symbols audited: `30`
- Fold-symbol rows audited: `47`
- Missing days represented by audited rows: `4757`
- Sum of missing benchmark weight over audited rows: `24.8470`
- Input reason: `missing_from_pit_panel` from strategy core reachability diagnostic.
- This is a read-only data coverage audit. It does not alter universe construction or strategy admission.

## Symbol Summary

| symbol | name | industry | folds | days | avg_rank | avg_weight | classification |
| --- | --- | --- | --- | --- | --- | --- | --- |
| SH.600000 | 浦发银行 | 银行 | 4 | 967 | 47.70 | 0.5281% | beyond_walk_forward_limit,ranked_out_or_balanced_out_of_pit_universe |
| SH.601816 | 京沪高铁 | 铁路 | 3 | 667 | 44.16 | 0.5637% | beyond_walk_forward_limit |
| SH.600837 |  |  | 3 | 708 | 52.02 | 0.4877% | beyond_walk_forward_limit |
| SH.600016 | 民生银行 | 银行 | 2 | 484 | 49.88 | 0.4939% | beyond_walk_forward_limit,ranked_out_or_balanced_out_of_pit_universe |
| SH.601328 | 交通银行 | 银行 | 1 | 241 | 20.22 | 0.8665% | beyond_walk_forward_limit |
| SH.601229 | 上海银行 | 银行 | 3 | 309 | 56.24 | 0.4525% | beyond_walk_forward_limit |
| SH.603288 | 海天味业 | 食品 | 1 | 243 | 39.98 | 0.5741% | beyond_walk_forward_limit |
| SH.601169 | 北京银行 | 银行 | 2 | 182 | 61.67 | 0.4368% | beyond_walk_forward_limit,ranked_out_or_balanced_out_of_pit_universe |
| SZ.300498 | 温氏股份 | 农业综合 | 2 | 159 | 60.61 | 0.4349% | beyond_walk_forward_limit |
| SH.600089 | 特变电工 | 电气设备 | 1 | 115 | 51.25 | 0.4881% | beyond_walk_forward_limit |
| SH.601766 | 中国中车 | 运输设备 | 2 | 128 | 68.11 | 0.3868% | beyond_walk_forward_limit |
| SH.600050 | 中国联通 | 电信运营 | 1 | 81 | 47.00 | 0.5098% | beyond_walk_forward_limit |
| SH.600104 | 上汽集团 | 汽车整车 | 2 | 80 | 68.49 | 0.4176% | beyond_walk_forward_limit |
| SH.601728 | 中国电信 | 电信运营 | 1 | 58 | 60.97 | 0.4225% | beyond_walk_forward_limit |
| SH.688041 | 海光信息 | 半导体 | 2 | 52 | 48.52 | 0.5421% | beyond_walk_forward_limit,universe_member_but_panel_missing |
| SH.601211 | 国泰海通 | 证券 | 2 | 60 | 71.30 | 0.3998% | beyond_walk_forward_limit,universe_member_but_panel_missing |
| SZ.002028 | 思源电气 | 电气设备 | 1 | 36 | 48.64 | 0.5074% | beyond_walk_forward_limit |
| SZ.000425 | 徐工机械 | 工程机械 | 1 | 42 | 59.90 | 0.4328% | beyond_walk_forward_limit |
| SH.600900 | 长江电力 | 水力发电 | 2 | 11 | 10.30 | 1.3323% | universe_member_but_panel_missing |
| SH.600745 | *ST闻泰 | 半导体 | 1 | 19 | 60.11 | 0.4397% | filtered_out_before_universe_selection |
| SH.601009 | 南京银行 | 银行 | 1 | 20 | 70.00 | 0.4027% | ranked_out_or_balanced_out_of_pit_universe |
| SH.601818 | 光大银行 | 银行 | 1 | 20 | 72.05 | 0.3936% | beyond_walk_forward_limit |
| SZ.002410 | 广联达 | 软件服务 | 1 | 18 | 73.00 | 0.3733% | beyond_walk_forward_limit |
| SH.600030 | 中信证券 | 证券 | 1 | 6 | 15.00 | 1.0202% | universe_member_but_panel_missing |
| SH.601088 | 中国神华 | 煤炭开采 | 1 | 10 | 36.00 | 0.5758% | universe_member_but_panel_missing |
| SH.688981 | 中芯国际 | 半导体 | 1 | 6 | 21.00 | 0.9513% | universe_member_but_panel_missing |
| SH.600150 | 中国船舶 | 船舶 | 1 | 10 | 59.00 | 0.4659% | universe_member_but_panel_missing |
| SH.603019 | 中科曙光 | IT设备 | 1 | 10 | 52.80 | 0.4620% | universe_member_but_panel_missing |
| SZ.002142 | 宁波银行 | 银行 | 1 | 6 | 29.17 | 0.7136% | universe_member_but_panel_missing |
| SH.688012 | DR中微公 | 半导体 | 1 | 9 | 49.00 | 0.4705% | universe_member_but_panel_missing |

## Classification Counts

| classification | fold_symbol_rows | missing_days | missing_weight |
| --- | --- | --- | --- |
| beyond_walk_forward_limit | 31 | 4078 | 21.4540 |
| universe_member_but_panel_missing | 11 | 80 | 0.5573 |
| ranked_out_or_balanced_out_of_pit_universe | 4 | 580 | 2.7521 |
| filtered_out_before_universe_selection | 1 | 19 | 0.0835 |

## Fold Classification Weights

| fold | classification | missing_days | missing_weight |
| --- | --- | --- | --- |
| 1 | beyond_walk_forward_limit | 220 | 1.0210 |
| 1 | universe_member_but_panel_missing | 22 | 0.2181 |
| 1 | filtered_out_before_universe_selection | 19 | 0.0835 |
| 2 | beyond_walk_forward_limit | 1377 | 6.8250 |
| 2 | universe_member_but_panel_missing | 1 | 0.0152 |
| 3 | beyond_walk_forward_limit | 902 | 5.6921 |
| 3 | ranked_out_or_balanced_out_of_pit_universe | 560 | 2.6715 |
| 4 | beyond_walk_forward_limit | 644 | 3.2175 |
| 4 | universe_member_but_panel_missing | 12 | 0.0547 |
| 5 | beyond_walk_forward_limit | 935 | 4.6985 |
| 5 | universe_member_but_panel_missing | 45 | 0.2693 |
| 5 | ranked_out_or_balanced_out_of_pit_universe | 20 | 0.0805 |
