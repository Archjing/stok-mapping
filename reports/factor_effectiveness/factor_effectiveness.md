# Factor Effectiveness Diagnostic

## Running Assumptions

- Price adjustment: qfq_asof, recomputed per historical as-of fold.
- Universe: point-in-time universe from each fold train-end date.
- Forward return label: same-symbol close.shift(-20) / close - 1 inside validation folds only.
- Valid fold count: 4.
- This report is a factor diagnostic only; it is not proof that a strategy is ready for live simulation.

## Conclusion

- use: 6 (low_pb, low_vol60, low_turnover_rate, low_vol20, ep, cash_flow_quality)
- observe: 1 (reversal_mom3)
- reject: 8 (reversal_mom5, low_amount_ratio20, profit_growth, roe, mom20, revenue_growth, mom60, low_debt_to_asset)
- missing: 0 (None)

## Factor Summary

| factor | coverage_ratio | mean_rank_ic | icir | positive_ic_ratio | long_short_return_mean | annual_turnover_proxy | recommendation | main_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| low_pb | 1.0000 | 0.0997 | 0.4017 | 0.6498 | 0.0166 | 2.0728 | use | positive IC and positive top-bottom return |
| low_vol60 | 0.7454 | 0.0974 | 0.3259 | 0.6243 | 0.0121 | 9.0564 | use | positive IC and positive top-bottom return |
| low_turnover_rate | 1.0000 | 0.0863 | 0.3087 | 0.6250 | 0.0048 | 49.7249 | use | positive IC and positive top-bottom return |
| low_vol20 | 1.0000 | 0.0846 | 0.3157 | 0.6336 | 0.0065 | 21.1812 | use | positive IC and positive top-bottom return |
| ep | 0.9519 | 0.0828 | 0.2887 | 0.5959 | 0.0083 | 3.9074 | use | positive IC and positive top-bottom return |
| cash_flow_quality | 0.9959 | 0.0554 | 0.5019 | 0.7123 | 0.0081 | 2.2767 | use | positive IC and positive top-bottom return |
| reversal_mom3 | 1.0000 | -0.0023 | -0.0107 | 0.4731 | 0.0005 | 116.3495 | observe | weak but non-negative IC or top-bottom return |
| reversal_mom5 | 1.0000 | -0.0021 | -0.0097 | 0.4612 | -0.0002 | 91.1699 | reject | negative IC and no positive top-bottom return |
| low_amount_ratio20 | 1.0000 | -0.0082 | -0.0506 | 0.4655 | -0.0025 | 134.1440 | reject | negative IC and no positive top-bottom return |
| profit_growth | 0.9959 | -0.0260 | -0.1524 | 0.4310 | -0.0014 | 2.1748 | reject | negative IC and no positive top-bottom return |
| roe | 0.9959 | -0.0263 | -0.1639 | 0.4407 | -0.0123 | 3.6699 | reject | negative IC and no positive top-bottom return |
| mom20 | 1.0000 | -0.0357 | -0.1569 | 0.4806 | -0.0081 | 44.2427 | reject | negative IC and no positive top-bottom return |
| revenue_growth | 0.9959 | -0.0498 | -0.2693 | 0.3836 | -0.0078 | 1.8123 | reject | negative IC and no positive top-bottom return |
| mom60 | 1.0000 | -0.0540 | -0.2341 | 0.4300 | -0.0116 | 25.9385 | reject | negative IC and no positive top-bottom return |
| low_debt_to_asset | 0.9959 | -0.0658 | -0.3451 | 0.3793 | -0.0137 | 0.8722 | reject | negative IC and no positive top-bottom return |

## Group Returns Summary

| factor | group | mean_forward_return | sample_count |
| --- | --- | --- | --- |
| cash_flow_quality | 1 | -0.0046 | 21741 |
| cash_flow_quality | 2 | -0.0093 | 22262 |
| cash_flow_quality | 3 | -0.0097 | 22249 |
| cash_flow_quality | 4 | 0.0023 | 22262 |
| cash_flow_quality | 5 | 0.0035 | 22272 |
| ep | 1 | -0.0052 | 20884 |
| ep | 2 | -0.0077 | 21129 |
| ep | 3 | -0.0052 | 21309 |
| ep | 4 | -0.0038 | 21129 |
| ep | 5 | 0.0031 | 21436 |
| low_amount_ratio20 | 1 | -0.0025 | 22180 |
| low_amount_ratio20 | 2 | -0.0030 | 22272 |
| low_amount_ratio20 | 3 | -0.0028 | 22244 |
| low_amount_ratio20 | 4 | -0.0045 | 22272 |
| low_amount_ratio20 | 5 | -0.0050 | 22272 |
| low_debt_to_asset | 1 | 0.0053 | 21741 |
| low_debt_to_asset | 2 | -0.0050 | 22262 |
| low_debt_to_asset | 3 | -0.0033 | 22249 |
| low_debt_to_asset | 4 | -0.0061 | 22262 |
| low_debt_to_asset | 5 | -0.0084 | 22272 |
| low_pb | 1 | -0.0107 | 22180 |
| low_pb | 2 | -0.0045 | 22272 |
| low_pb | 3 | -0.0065 | 22244 |
| low_pb | 4 | -0.0022 | 22272 |
| low_pb | 5 | 0.0060 | 22272 |
| low_turnover_rate | 1 | -0.0038 | 22180 |
| low_turnover_rate | 2 | -0.0061 | 22272 |
| low_turnover_rate | 3 | -0.0072 | 22244 |
| low_turnover_rate | 4 | -0.0017 | 22272 |
| low_turnover_rate | 5 | 0.0010 | 22272 |
| low_vol20 | 1 | -0.0040 | 22180 |
| low_vol20 | 2 | -0.0061 | 22272 |
| low_vol20 | 3 | -0.0051 | 22244 |
| low_vol20 | 4 | -0.0051 | 22272 |
| low_vol20 | 5 | 0.0025 | 22272 |
| low_vol60 | 1 | -0.0095 | 16517 |
| low_vol60 | 2 | -0.0143 | 16607 |
| low_vol60 | 3 | -0.0041 | 16581 |
| low_vol60 | 4 | -0.0059 | 16607 |
| low_vol60 | 5 | 0.0026 | 16608 |
| mom20 | 1 | -0.0009 | 22180 |
| mom20 | 2 | -0.0020 | 22272 |
| mom20 | 3 | -0.0017 | 22244 |
| mom20 | 4 | -0.0043 | 22272 |
| mom20 | 5 | -0.0090 | 22272 |
| mom60 | 1 | 0.0014 | 22180 |
| mom60 | 2 | -0.0010 | 22272 |
| mom60 | 3 | -0.0022 | 22244 |
| mom60 | 4 | -0.0058 | 22272 |
| mom60 | 5 | -0.0102 | 22272 |
| profit_growth | 1 | -0.0056 | 21741 |
| profit_growth | 2 | -0.0005 | 22262 |
| profit_growth | 3 | -0.0023 | 22249 |
| profit_growth | 4 | -0.0024 | 22262 |
| profit_growth | 5 | -0.0070 | 22272 |
| revenue_growth | 1 | -0.0002 | 21741 |
| revenue_growth | 2 | -0.0015 | 22262 |
| revenue_growth | 3 | -0.0024 | 22249 |
| revenue_growth | 4 | -0.0057 | 22262 |
| revenue_growth | 5 | -0.0080 | 22272 |
| reversal_mom3 | 1 | -0.0051 | 22180 |
| reversal_mom3 | 2 | -0.0025 | 22272 |
| reversal_mom3 | 3 | -0.0027 | 22244 |
| reversal_mom3 | 4 | -0.0029 | 22272 |
| reversal_mom3 | 5 | -0.0046 | 22272 |
| reversal_mom5 | 1 | -0.0052 | 22180 |
| reversal_mom5 | 2 | -0.0027 | 22272 |
| reversal_mom5 | 3 | -0.0020 | 22244 |
| reversal_mom5 | 4 | -0.0027 | 22272 |
| reversal_mom5 | 5 | -0.0054 | 22272 |
| roe | 1 | -0.0018 | 21741 |
| roe | 2 | 0.0014 | 22262 |
| roe | 3 | -0.0023 | 22249 |
| roe | 4 | -0.0009 | 22262 |
| roe | 5 | -0.0141 | 22272 |

## Yearly IC Summary

| factor | year | mean_rank_ic | icir | positive_ic_ratio | sample_days |
| --- | --- | --- | --- | --- | --- |
| cash_flow_quality | 2021 | 0.0069 | 0.0826 | 0.5959 | 146 |
| cash_flow_quality | 2022 | 0.0289 | 0.3161 | 0.6667 | 222 |
| cash_flow_quality | 2023 | 0.1216 | 1.1012 | 0.8378 | 222 |
| cash_flow_quality | 2024 | 0.0500 | 0.4367 | 0.7117 | 222 |
| cash_flow_quality | 2025 | 0.0508 | 0.4646 | 0.7069 | 116 |
| ep | 2021 | 0.0855 | 0.2562 | 0.5548 | 146 |
| ep | 2022 | 0.0672 | 0.2428 | 0.5405 | 222 |
| ep | 2023 | 0.1178 | 0.4538 | 0.6126 | 222 |
| ep | 2024 | 0.0290 | 0.1006 | 0.5811 | 222 |
| ep | 2025 | 0.1455 | 0.5346 | 0.7500 | 116 |
| low_amount_ratio20 | 2021 | -0.0404 | -0.2623 | 0.3836 | 146 |
| low_amount_ratio20 | 2022 | 0.0003 | 0.0022 | 0.4955 | 222 |
| low_amount_ratio20 | 2023 | -0.0058 | -0.0366 | 0.4505 | 222 |
| low_amount_ratio20 | 2024 | -0.0048 | -0.0274 | 0.4955 | 222 |
| low_amount_ratio20 | 2025 | 0.0046 | 0.0282 | 0.4828 | 116 |
| low_debt_to_asset | 2021 | -0.0951 | -0.4802 | 0.3630 | 146 |
| low_debt_to_asset | 2022 | -0.0328 | -0.1963 | 0.4775 | 222 |
| low_debt_to_asset | 2023 | -0.0748 | -0.3437 | 0.4099 | 222 |
| low_debt_to_asset | 2024 | -0.0660 | -0.3236 | 0.3063 | 222 |
| low_debt_to_asset | 2025 | -0.0741 | -0.6022 | 0.2931 | 116 |
| low_pb | 2021 | 0.1154 | 0.3854 | 0.5890 | 146 |
| low_pb | 2022 | 0.0994 | 0.4044 | 0.6306 | 222 |
| low_pb | 2023 | 0.1634 | 0.7373 | 0.7523 | 222 |
| low_pb | 2024 | 0.0386 | 0.1547 | 0.6081 | 222 |
| low_pb | 2025 | 0.0754 | 0.3911 | 0.6466 | 116 |
| low_turnover_rate | 2021 | 0.0464 | 0.1782 | 0.5274 | 146 |
| low_turnover_rate | 2022 | 0.1011 | 0.4023 | 0.6577 | 222 |
| low_turnover_rate | 2023 | 0.1656 | 0.7134 | 0.7432 | 222 |
| low_turnover_rate | 2024 | 0.0462 | 0.1383 | 0.6036 | 222 |
| low_turnover_rate | 2025 | 0.0334 | 0.1146 | 0.5000 | 116 |
| low_vol20 | 2021 | 0.0861 | 0.3733 | 0.6849 | 146 |
| low_vol20 | 2022 | 0.0388 | 0.1763 | 0.5811 | 222 |
| low_vol20 | 2023 | 0.1679 | 0.7538 | 0.7477 | 222 |
| low_vol20 | 2024 | 0.0843 | 0.2753 | 0.6396 | 222 |
| low_vol20 | 2025 | 0.0113 | 0.0327 | 0.4397 | 116 |
| low_vol60 | 2021 | 0.1671 | 0.8162 | 0.7471 | 87 |
| low_vol60 | 2022 | 0.0400 | 0.1515 | 0.5092 | 163 |
| low_vol60 | 2023 | 0.1342 | 0.5652 | 0.6933 | 163 |
| low_vol60 | 2024 | 0.1295 | 0.3744 | 0.7117 | 163 |
| low_vol60 | 2025 | 0.0290 | 0.0768 | 0.4741 | 116 |
| mom20 | 2021 | -0.0169 | -0.0701 | 0.5274 | 146 |
| mom20 | 2022 | -0.0781 | -0.3529 | 0.3919 | 222 |
| mom20 | 2023 | -0.0091 | -0.0505 | 0.5315 | 222 |
| mom20 | 2024 | -0.0111 | -0.0451 | 0.5045 | 222 |
| mom20 | 2025 | -0.0760 | -0.3048 | 0.4483 | 116 |
| mom60 | 2021 | -0.0773 | -0.3127 | 0.3767 | 146 |
| mom60 | 2022 | -0.0940 | -0.4414 | 0.3423 | 222 |
| mom60 | 2023 | 0.0063 | 0.0341 | 0.5721 | 222 |
| mom60 | 2024 | -0.0318 | -0.1158 | 0.4640 | 222 |
| mom60 | 2025 | -0.1064 | -0.5367 | 0.3276 | 116 |
| profit_growth | 2021 | -0.0359 | -0.1723 | 0.4178 | 146 |
| profit_growth | 2022 | -0.0628 | -0.3295 | 0.3874 | 222 |
| profit_growth | 2023 | -0.0578 | -0.4295 | 0.3063 | 222 |
| profit_growth | 2024 | 0.0008 | 0.0047 | 0.4414 | 222 |
| profit_growth | 2025 | 0.0667 | 0.6676 | 0.7500 | 116 |
| revenue_growth | 2021 | -0.0642 | -0.3424 | 0.3425 | 146 |
| revenue_growth | 2022 | -0.0597 | -0.2622 | 0.4054 | 222 |
| revenue_growth | 2023 | -0.0885 | -0.5208 | 0.2658 | 222 |
| revenue_growth | 2024 | -0.0253 | -0.1654 | 0.4459 | 222 |
| revenue_growth | 2025 | 0.0145 | 0.0972 | 0.5000 | 116 |
| reversal_mom3 | 2021 | 0.0010 | 0.0050 | 0.5000 | 146 |
| reversal_mom3 | 2022 | 0.0068 | 0.0317 | 0.4955 | 222 |
| reversal_mom3 | 2023 | -0.0213 | -0.1128 | 0.4279 | 222 |
| reversal_mom3 | 2024 | -0.0006 | -0.0028 | 0.5090 | 222 |
| reversal_mom3 | 2025 | 0.0095 | 0.0394 | 0.4138 | 116 |
| reversal_mom5 | 2021 | -0.0039 | -0.0203 | 0.5068 | 146 |
| reversal_mom5 | 2022 | 0.0136 | 0.0620 | 0.5135 | 222 |
| reversal_mom5 | 2023 | -0.0248 | -0.1243 | 0.4099 | 222 |
| reversal_mom5 | 2024 | 0.0012 | 0.0053 | 0.4550 | 222 |
| reversal_mom5 | 2025 | 0.0071 | 0.0277 | 0.4138 | 116 |
| roe | 2021 | -0.0739 | -0.5384 | 0.3082 | 146 |
| roe | 2022 | -0.0196 | -0.1648 | 0.4505 | 222 |
| roe | 2023 | -0.0414 | -0.2111 | 0.3829 | 222 |
| roe | 2024 | -0.0319 | -0.2117 | 0.4459 | 222 |
| roe | 2025 | 0.0602 | 0.3547 | 0.6897 | 116 |

## Factor Correlation

| factor | low_vol20 | low_vol60 | low_turnover_rate | low_amount_ratio20 | mom20 | mom60 | reversal_mom3 | reversal_mom5 | roe | cash_flow_quality | profit_growth | revenue_growth | low_debt_to_asset | ep | low_pb |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| low_vol20 | 1.0000 | 0.8446 | 0.6244 | -0.0374 | -0.0965 | -0.0789 | -0.0112 | 0.0038 | -0.0171 | 0.1140 | -0.1373 | -0.2188 | -0.2700 | 0.4372 | 0.4430 |
| low_vol60 | 0.8446 | 1.0000 | 0.6451 | -0.0515 | 0.0281 | 0.0006 | -0.0379 | -0.0315 | -0.0204 | 0.1360 | -0.1447 | -0.2463 | -0.3132 | 0.4792 | 0.4892 |
| low_turnover_rate | 0.6244 | 0.6451 | 1.0000 | 0.2600 | -0.0201 | 0.0319 | 0.0327 | 0.0316 | 0.0647 | 0.0923 | -0.1790 | -0.2114 | -0.2029 | 0.3769 | 0.3179 |
| low_amount_ratio20 | -0.0374 | -0.0515 | 0.2600 | 1.0000 | -0.1982 | -0.0623 | 0.2827 | 0.2975 | -0.0266 | -0.0055 | -0.0158 | -0.0152 | 0.0095 | -0.0036 | 0.0146 |
| mom20 | -0.0965 | 0.0281 | -0.0201 | -0.1982 | 1.0000 | 0.4825 | -0.3318 | -0.4414 | -0.0062 | 0.0463 | 0.0028 | -0.0228 | -0.0620 | -0.0052 | 0.0032 |
| mom60 | -0.0789 | 0.0006 | 0.0319 | -0.0623 | 0.4825 | 1.0000 | -0.1780 | -0.2282 | -0.0311 | 0.0657 | 0.0218 | -0.0296 | -0.0906 | -0.0310 | -0.0163 |
| reversal_mom3 | -0.0112 | -0.0379 | 0.0327 | 0.2827 | -0.3318 | -0.1780 | 1.0000 | 0.7231 | 0.0071 | -0.0246 | 0.0035 | 0.0168 | 0.0364 | -0.0117 | -0.0155 |
| reversal_mom5 | 0.0038 | -0.0315 | 0.0316 | 0.2975 | -0.4414 | -0.2282 | 0.7231 | 1.0000 | 0.0063 | -0.0271 | 0.0018 | 0.0166 | 0.0406 | -0.0076 | -0.0120 |
| roe | -0.0171 | -0.0204 | 0.0647 | -0.0266 | -0.0062 | -0.0311 | 0.0071 | 0.0063 | 1.0000 | -0.0530 | 0.3996 | 0.3659 | 0.2231 | 0.1472 | -0.3321 |
| cash_flow_quality | 0.1140 | 0.1360 | 0.0923 | -0.0055 | 0.0463 | 0.0657 | -0.0246 | -0.0271 | -0.0530 | 1.0000 | 0.0046 | -0.0433 | -0.1176 | 0.0489 | 0.1434 |
| profit_growth | -0.1373 | -0.1447 | -0.1790 | -0.0158 | 0.0028 | 0.0218 | 0.0035 | 0.0018 | 0.3996 | 0.0046 | 1.0000 | 0.6122 | 0.1030 | -0.1077 | -0.2578 |
| revenue_growth | -0.2188 | -0.2463 | -0.2114 | -0.0152 | -0.0228 | -0.0296 | 0.0168 | 0.0166 | 0.3659 | -0.0433 | 0.6122 | 1.0000 | 0.1770 | -0.2211 | -0.3652 |
| low_debt_to_asset | -0.2700 | -0.3132 | -0.2029 | 0.0095 | -0.0620 | -0.0906 | 0.0364 | 0.0406 | 0.2231 | -0.1176 | 0.1030 | 0.1770 | 1.0000 | -0.4727 | -0.5524 |
| ep | 0.4372 | 0.4792 | 0.3769 | -0.0036 | -0.0052 | -0.0310 | -0.0117 | -0.0076 | 0.1472 | 0.0489 | -0.1077 | -0.2211 | -0.4727 | 1.0000 | 0.7552 |
| low_pb | 0.4430 | 0.4892 | 0.3179 | 0.0146 | 0.0032 | -0.0163 | -0.0155 | -0.0120 | -0.3321 | 0.1434 | -0.2578 | -0.3652 | -0.5524 | 0.7552 | 1.0000 |

## Warnings / Data Coverage

- No material warning generated by this diagnostic run.
