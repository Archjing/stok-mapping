# Missing Core Member Audit

Generated at: 2026-06-25T12:22:55

## Scope

- Top symbols audited: `30`
- Fold-symbol rows audited: `67`
- Missing days represented by audited rows: `10328`
- Sum of missing benchmark weight over audited rows: `53.2842`
- Input reason: `missing_from_pit_panel` from strategy core reachability diagnostic.
- This is a read-only data coverage audit. It does not alter universe construction or strategy admission.

## Symbol Summary

| symbol | name | industry | folds | days | avg_rank | avg_weight | classification |
| --- | --- | --- | --- | --- | --- | --- | --- |
| SH.601816 | 京沪高铁 | 铁路 | 5 | 1150 | 37.33 | 0.6263% | beyond_walk_forward_limit |
| SH.601328 | 交通银行 | 银行 | 3 | 727 | 27.74 | 0.7339% | beyond_walk_forward_limit |
| SH.600000 | 浦发银行 | 银行 | 4 | 967 | 47.70 | 0.5281% | beyond_walk_forward_limit,ranked_out_or_balanced_out_of_pit_universe |
| SH.600016 | 民生银行 | 银行 | 5 | 1008 | 51.60 | 0.4883% | beyond_walk_forward_limit,ranked_out_or_balanced_out_of_pit_universe |
| SH.600837 |  |  | 4 | 930 | 50.21 | 0.5018% | beyond_walk_forward_limit |
| SH.600406 | 国电南瑞 | 电气设备 | 4 | 782 | 52.72 | 0.4842% | beyond_walk_forward_limit |
| SZ.300498 | 温氏股份 | 农业综合 | 3 | 400 | 56.14 | 0.4642% | beyond_walk_forward_limit |
| SH.600660 | 福耀玻璃 | 汽车配件 | 2 | 427 | 60.02 | 0.4391% | beyond_walk_forward_limit |
| SH.603288 | 海天味业 | 食品 | 2 | 346 | 49.61 | 0.5170% | beyond_walk_forward_limit |
| SH.601169 | 北京银行 | 银行 | 3 | 402 | 61.97 | 0.4408% | beyond_walk_forward_limit,ranked_out_or_balanced_out_of_pit_universe |
| SH.600919 | 江苏银行 | 银行 | 2 | 300 | 52.66 | 0.4945% | beyond_walk_forward_limit |
| SH.601229 | 上海银行 | 银行 | 3 | 309 | 56.24 | 0.4525% | beyond_walk_forward_limit |
| SH.601766 | 中国中车 | 运输设备 | 3 | 304 | 67.77 | 0.3967% | beyond_walk_forward_limit |
| SZ.000792 | 盐湖股份 | 农药化肥 | 2 | 243 | 57.17 | 0.4599% | beyond_walk_forward_limit |
| SH.601988 | 中国银行 | 银行 | 1 | 223 | 57.33 | 0.4609% | beyond_walk_forward_limit |
| SH.688981 | 中芯国际 | 半导体 | 2 | 226 | 41.73 | 0.6926% | beyond_walk_forward_limit,universe_member_but_panel_missing |
| SH.600436 | 片仔癀 | 中成药 | 1 | 205 | 60.79 | 0.4436% | beyond_walk_forward_limit |
| SH.600111 | 北方稀土 | 小金属 | 1 | 159 | 47.29 | 0.5142% | beyond_walk_forward_limit |
| SZ.002352 | 顺丰控股 | 仓储物流 | 1 | 143 | 46.98 | 0.5051% | beyond_walk_forward_limit |
| SH.601688 | 华泰证券 | 证券 | 1 | 161 | 63.01 | 0.4380% | beyond_walk_forward_limit |
| SH.600104 | 上汽集团 | 汽车整车 | 3 | 168 | 68.53 | 0.4096% | beyond_walk_forward_limit |
| SH.600089 | 特变电工 | 电气设备 | 1 | 115 | 51.25 | 0.4881% | beyond_walk_forward_limit |
| SZ.002142 | 宁波银行 | 银行 | 2 | 126 | 45.70 | 0.5699% | beyond_walk_forward_limit,universe_member_but_panel_missing |
| SH.601211 | 国泰海通 | 证券 | 2 | 118 | 70.23 | 0.4079% | beyond_walk_forward_limit |
| SZ.000338 | 潍柴动力 | 汽车配件 | 1 | 101 | 58.93 | 0.4588% | beyond_walk_forward_limit |
| SH.600050 | 中国联通 | 电信运营 | 1 | 81 | 47.00 | 0.5098% | beyond_walk_forward_limit |
| SH.600028 | 中国石化 | 石油加工 | 1 | 61 | 68.92 | 0.4118% | beyond_walk_forward_limit |
| SH.601728 | 中国电信 | 电信运营 | 1 | 58 | 60.97 | 0.4225% | beyond_walk_forward_limit |
| SH.688041 | 海光信息 | 半导体 | 2 | 52 | 48.52 | 0.5421% | beyond_walk_forward_limit,universe_member_but_panel_missing |
| SZ.002028 | 思源电气 | 电气设备 | 1 | 36 | 48.64 | 0.5074% | beyond_walk_forward_limit |

## Classification Counts

| classification | fold_symbol_rows | missing_days | missing_weight |
| --- | --- | --- | --- |
| beyond_walk_forward_limit | 61 | 9746 | 50.4466 |
| universe_member_but_panel_missing | 3 | 22 | 0.1660 |
| ranked_out_or_balanced_out_of_pit_universe | 3 | 560 | 2.6715 |

## Fold Classification Weights

| fold | classification | missing_days | missing_weight |
| --- | --- | --- | --- |
| 1 | beyond_walk_forward_limit | 1002 | 5.3171 |
| 1 | universe_member_but_panel_missing | 6 | 0.0428 |
| 2 | beyond_walk_forward_limit | 1928 | 9.8196 |
| 3 | beyond_walk_forward_limit | 2315 | 12.3858 |
| 3 | ranked_out_or_balanced_out_of_pit_universe | 560 | 2.6715 |
| 4 | beyond_walk_forward_limit | 2272 | 11.6945 |
| 5 | beyond_walk_forward_limit | 2229 | 11.2296 |
| 5 | universe_member_but_panel_missing | 16 | 0.1232 |
