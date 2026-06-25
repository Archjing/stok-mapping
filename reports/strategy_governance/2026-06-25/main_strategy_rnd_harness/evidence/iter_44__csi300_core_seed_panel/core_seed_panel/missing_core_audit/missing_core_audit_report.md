# Missing Core Member Audit

Generated at: 2026-06-25T13:10:47

## Scope

- Top symbols audited: `30`
- Fold-symbol rows audited: `12`
- Missing days represented by audited rows: `134`
- Sum of missing benchmark weight over audited rows: `0.8236`
- Input reason: `missing_from_pit_panel` from strategy core reachability diagnostic.
- This is a read-only data coverage audit. It does not alter universe construction or strategy admission.

## Symbol Summary

| symbol | name | industry | folds | days | avg_rank | avg_weight | classification |
| --- | --- | --- | --- | --- | --- | --- | --- |
| SH.600837 |  |  | 1 | 54 | 48.43 | 0.4932% | beyond_walk_forward_limit |
| SH.600900 | 长江电力 | 水力发电 | 2 | 11 | 10.30 | 1.3323% | universe_member_but_panel_missing |
| SH.688041 | 海光信息 | 半导体 | 1 | 10 | 30.00 | 0.6614% | universe_member_but_panel_missing |
| SH.600030 | 中信证券 | 证券 | 1 | 6 | 15.00 | 1.0202% | universe_member_but_panel_missing |
| SH.601088 | 中国神华 | 煤炭开采 | 1 | 10 | 36.00 | 0.5758% | universe_member_but_panel_missing |
| SH.688981 | 中芯国际 | 半导体 | 1 | 6 | 21.00 | 0.9513% | universe_member_but_panel_missing |
| SH.600150 | 中国船舶 | 船舶 | 1 | 10 | 59.00 | 0.4659% | universe_member_but_panel_missing |
| SH.603019 | 中科曙光 | IT设备 | 1 | 10 | 52.80 | 0.4620% | universe_member_but_panel_missing |
| SZ.002142 | 宁波银行 | 银行 | 1 | 6 | 29.17 | 0.7136% | universe_member_but_panel_missing |
| SH.688012 | DR中微公 | 半导体 | 1 | 9 | 49.00 | 0.4705% | universe_member_but_panel_missing |
| SH.601211 | 国泰海通 | 证券 | 1 | 2 | 71.00 | 0.4033% | beyond_walk_forward_limit |

## Classification Counts

| classification | fold_symbol_rows | missing_days | missing_weight |
| --- | --- | --- | --- |
| universe_member_but_panel_missing | 10 | 78 | 0.5492 |
| beyond_walk_forward_limit | 2 | 56 | 0.2744 |

## Fold Classification Weights

| fold | classification | missing_days | missing_weight |
| --- | --- | --- | --- |
| 1 | universe_member_but_panel_missing | 22 | 0.2181 |
| 2 | universe_member_but_panel_missing | 1 | 0.0152 |
| 4 | beyond_walk_forward_limit | 56 | 0.2744 |
| 4 | universe_member_but_panel_missing | 10 | 0.0466 |
| 5 | universe_member_but_panel_missing | 45 | 0.2693 |
