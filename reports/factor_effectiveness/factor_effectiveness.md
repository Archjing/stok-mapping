# Factor Effectiveness Diagnostic

## Running Assumptions

- Price adjustment: qfq_asof, recomputed per historical as-of fold.
- Universe: point-in-time universe from each fold train-end date.
- Forward return label: same-symbol close.shift(-20) / close - 1 inside validation folds only.
- Valid fold count: 4.
- This report is a factor diagnostic only; it is not proof that a strategy is ready for live simulation.

## Conclusion

- use: 6 (low_pb, low_vol60, low_turnover_rate, low_vol20, ep, cash_flow_quality)
- observe: 2 (reversal_mom3, profit_growth)
- reject: 7 (reversal_mom5, low_amount_ratio20, roe, mom20, revenue_growth, mom60, low_debt_to_asset)
- missing: 0 (None)

## Factor Summary

| factor | coverage_ratio | mean_rank_ic | icir | positive_ic_ratio | long_short_return_mean | annual_turnover_proxy | recommendation | main_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| low_pb | 1.0000 | 0.0945 | 0.3809 | 0.6412 | 0.0150 | 1.9369 | use | positive IC and positive top-bottom return |
| low_vol60 | 0.7455 | 0.0934 | 0.3137 | 0.6171 | 0.0099 | 8.8285 | use | positive IC and positive top-bottom return |
| low_turnover_rate | 1.0000 | 0.0860 | 0.3021 | 0.6207 | 0.0039 | 50.2460 | use | positive IC and positive top-bottom return |
| low_vol20 | 1.0000 | 0.0816 | 0.3048 | 0.6379 | 0.0053 | 20.7961 | use | positive IC and positive top-bottom return |
| ep | 0.9559 | 0.0775 | 0.2715 | 0.5959 | 0.0071 | 3.5660 | use | positive IC and positive top-bottom return |
| cash_flow_quality | 0.9959 | 0.0535 | 0.4891 | 0.6918 | 0.0067 | 2.2087 | use | positive IC and positive top-bottom return |
| reversal_mom3 | 1.0000 | -0.0018 | -0.0083 | 0.4731 | 0.0004 | 116.4968 | observe | weak but non-negative IC or top-bottom return |
| profit_growth | 0.9959 | -0.0178 | -0.0997 | 0.4515 | 0.0017 | 2.1861 | observe | weak but non-negative IC or top-bottom return |
| reversal_mom5 | 1.0000 | -0.0013 | -0.0059 | 0.4752 | -0.0002 | 91.4191 | reject | negative IC and no positive top-bottom return |
| low_amount_ratio20 | 1.0000 | -0.0080 | -0.0497 | 0.4612 | -0.0022 | 134.2233 | reject | negative IC and no positive top-bottom return |
| roe | 0.9959 | -0.0247 | -0.1490 | 0.4591 | -0.0093 | 4.1796 | reject | negative IC and no positive top-bottom return |
| mom20 | 1.0000 | -0.0361 | -0.1601 | 0.4838 | -0.0077 | 43.9369 | reject | negative IC and no positive top-bottom return |
| revenue_growth | 0.9959 | -0.0416 | -0.2176 | 0.4159 | -0.0060 | 1.8236 | reject | negative IC and no positive top-bottom return |
| mom60 | 1.0000 | -0.0495 | -0.2139 | 0.4310 | -0.0094 | 26.4256 | reject | negative IC and no positive top-bottom return |
| low_debt_to_asset | 0.9959 | -0.0644 | -0.3461 | 0.3890 | -0.0130 | 0.8382 | reject | negative IC and no positive top-bottom return |

## Group Returns Summary

| factor | group | mean_forward_return | sample_count |
| --- | --- | --- | --- |
| cash_flow_quality | 1 | -0.0033 | 21771 |
| cash_flow_quality | 2 | -0.0091 | 22262 |
| cash_flow_quality | 3 | -0.0067 | 22254 |
| cash_flow_quality | 4 | 0.0009 | 22262 |
| cash_flow_quality | 5 | 0.0034 | 22272 |
| ep | 1 | -0.0036 | 20913 |
| ep | 2 | -0.0066 | 21351 |
| ep | 3 | -0.0052 | 21156 |
| ep | 4 | -0.0034 | 21351 |
| ep | 5 | 0.0034 | 21592 |
| low_amount_ratio20 | 1 | -0.0017 | 22210 |
| low_amount_ratio20 | 2 | -0.0027 | 22272 |
| low_amount_ratio20 | 3 | -0.0022 | 22249 |
| low_amount_ratio20 | 4 | -0.0044 | 22272 |
| low_amount_ratio20 | 5 | -0.0039 | 22272 |
| low_debt_to_asset | 1 | 0.0056 | 21771 |
| low_debt_to_asset | 2 | -0.0045 | 22262 |
| low_debt_to_asset | 3 | -0.0029 | 22254 |
| low_debt_to_asset | 4 | -0.0053 | 22262 |
| low_debt_to_asset | 5 | -0.0074 | 22272 |
| low_pb | 1 | -0.0088 | 22210 |
| low_pb | 2 | -0.0035 | 22272 |
| low_pb | 3 | -0.0064 | 22249 |
| low_pb | 4 | -0.0023 | 22272 |
| low_pb | 5 | 0.0062 | 22272 |
| low_turnover_rate | 1 | -0.0019 | 22210 |
| low_turnover_rate | 2 | -0.0058 | 22272 |
| low_turnover_rate | 3 | -0.0075 | 22249 |
| low_turnover_rate | 4 | -0.0016 | 22272 |
| low_turnover_rate | 5 | 0.0020 | 22272 |
| low_vol20 | 1 | -0.0024 | 22210 |
| low_vol20 | 2 | -0.0049 | 22272 |
| low_vol20 | 3 | -0.0057 | 22249 |
| low_vol20 | 4 | -0.0045 | 22272 |
| low_vol20 | 5 | 0.0028 | 22272 |
| low_vol60 | 1 | -0.0065 | 16547 |
| low_vol60 | 2 | -0.0148 | 16608 |
| low_vol60 | 3 | -0.0034 | 16584 |
| low_vol60 | 4 | -0.0056 | 16608 |
| low_vol60 | 5 | 0.0034 | 16608 |
| mom20 | 1 | -0.0001 | 22210 |
| mom20 | 2 | -0.0014 | 22272 |
| mom20 | 3 | -0.0015 | 22249 |
| mom20 | 4 | -0.0041 | 22272 |
| mom20 | 5 | -0.0078 | 22272 |
| mom60 | 1 | 0.0014 | 22210 |
| mom60 | 2 | -0.0006 | 22272 |
| mom60 | 3 | -0.0022 | 22249 |
| mom60 | 4 | -0.0055 | 22272 |
| mom60 | 5 | -0.0081 | 22272 |
| profit_growth | 1 | -0.0054 | 21771 |
| profit_growth | 2 | -0.0010 | 22262 |
| profit_growth | 3 | -0.0026 | 22254 |
| profit_growth | 4 | -0.0021 | 22262 |
| profit_growth | 5 | -0.0038 | 22272 |
| revenue_growth | 1 | 0.0017 | 21771 |
| revenue_growth | 2 | -0.0043 | 22262 |
| revenue_growth | 3 | -0.0032 | 22254 |
| revenue_growth | 4 | -0.0046 | 22262 |
| revenue_growth | 5 | -0.0043 | 22272 |
| reversal_mom3 | 1 | -0.0042 | 22210 |
| reversal_mom3 | 2 | -0.0021 | 22272 |
| reversal_mom3 | 3 | -0.0022 | 22249 |
| reversal_mom3 | 4 | -0.0026 | 22272 |
| reversal_mom3 | 5 | -0.0038 | 22272 |
| reversal_mom5 | 1 | -0.0043 | 22210 |
| reversal_mom5 | 2 | -0.0024 | 22272 |
| reversal_mom5 | 3 | -0.0015 | 22249 |
| reversal_mom5 | 4 | -0.0021 | 22272 |
| reversal_mom5 | 5 | -0.0045 | 22272 |
| roe | 1 | -0.0029 | 21771 |
| roe | 2 | 0.0027 | 22262 |
| roe | 3 | -0.0006 | 22254 |
| roe | 4 | -0.0018 | 22262 |
| roe | 5 | -0.0122 | 22272 |

## Yearly IC Summary

| factor | year | mean_rank_ic | icir | positive_ic_ratio | sample_days |
| --- | --- | --- | --- | --- | --- |
| cash_flow_quality | 2021 | 0.0004 | 0.0059 | 0.5625 | 144 |
| cash_flow_quality | 2022 | 0.0363 | 0.3893 | 0.6622 | 222 |
| cash_flow_quality | 2023 | 0.1156 | 1.0335 | 0.8153 | 222 |
| cash_flow_quality | 2024 | 0.0469 | 0.4052 | 0.6667 | 222 |
| cash_flow_quality | 2025 | 0.0463 | 0.4387 | 0.7203 | 118 |
| ep | 2021 | 0.0867 | 0.2580 | 0.5556 | 144 |
| ep | 2022 | 0.0714 | 0.2575 | 0.5495 | 222 |
| ep | 2023 | 0.1074 | 0.4190 | 0.6171 | 222 |
| ep | 2024 | 0.0213 | 0.0742 | 0.5766 | 222 |
| ep | 2025 | 0.1274 | 0.4723 | 0.7288 | 118 |
| low_amount_ratio20 | 2021 | -0.0388 | -0.2484 | 0.3889 | 144 |
| low_amount_ratio20 | 2022 | 0.0018 | 0.0116 | 0.4910 | 222 |
| low_amount_ratio20 | 2023 | -0.0029 | -0.0183 | 0.4820 | 222 |
| low_amount_ratio20 | 2024 | -0.0073 | -0.0422 | 0.4640 | 222 |
| low_amount_ratio20 | 2025 | -0.0003 | -0.0017 | 0.4492 | 118 |
| low_debt_to_asset | 2021 | -0.0924 | -0.4915 | 0.3958 | 144 |
| low_debt_to_asset | 2022 | -0.0391 | -0.2348 | 0.4775 | 222 |
| low_debt_to_asset | 2023 | -0.0728 | -0.3421 | 0.4189 | 222 |
| low_debt_to_asset | 2024 | -0.0601 | -0.3008 | 0.3153 | 222 |
| low_debt_to_asset | 2025 | -0.0702 | -0.5630 | 0.2966 | 118 |
| low_pb | 2021 | 0.1162 | 0.3881 | 0.5972 | 144 |
| low_pb | 2022 | 0.1008 | 0.4020 | 0.6216 | 222 |
| low_pb | 2023 | 0.1560 | 0.7150 | 0.7568 | 222 |
| low_pb | 2024 | 0.0319 | 0.1294 | 0.5991 | 222 |
| low_pb | 2025 | 0.0581 | 0.2993 | 0.5932 | 118 |
| low_turnover_rate | 2021 | 0.0452 | 0.1654 | 0.5208 | 144 |
| low_turnover_rate | 2022 | 0.1118 | 0.4331 | 0.6622 | 222 |
| low_turnover_rate | 2023 | 0.1691 | 0.7243 | 0.7658 | 222 |
| low_turnover_rate | 2024 | 0.0425 | 0.1274 | 0.5811 | 222 |
| low_turnover_rate | 2025 | 0.0124 | 0.0424 | 0.4661 | 118 |
| low_vol20 | 2021 | 0.0868 | 0.3723 | 0.6875 | 144 |
| low_vol20 | 2022 | 0.0476 | 0.2166 | 0.5991 | 222 |
| low_vol20 | 2023 | 0.1631 | 0.7364 | 0.7523 | 222 |
| low_vol20 | 2024 | 0.0798 | 0.2620 | 0.6532 | 222 |
| low_vol20 | 2025 | -0.0103 | -0.0299 | 0.4068 | 118 |
| low_vol60 | 2021 | 0.1657 | 0.7968 | 0.7529 | 85 |
| low_vol60 | 2022 | 0.0424 | 0.1612 | 0.5153 | 163 |
| low_vol60 | 2023 | 0.1325 | 0.5444 | 0.6871 | 163 |
| low_vol60 | 2024 | 0.1307 | 0.3925 | 0.7178 | 163 |
| low_vol60 | 2025 | 0.0063 | 0.0166 | 0.4237 | 118 |
| mom20 | 2021 | -0.0174 | -0.0702 | 0.5139 | 144 |
| mom20 | 2022 | -0.0830 | -0.3837 | 0.3829 | 222 |
| mom20 | 2023 | -0.0171 | -0.0962 | 0.5270 | 222 |
| mom20 | 2024 | -0.0054 | -0.0224 | 0.5135 | 222 |
| mom20 | 2025 | -0.0641 | -0.2573 | 0.5000 | 118 |
| mom60 | 2021 | -0.0813 | -0.3315 | 0.3472 | 144 |
| mom60 | 2022 | -0.0916 | -0.4260 | 0.3468 | 222 |
| mom60 | 2023 | 0.0078 | 0.0414 | 0.5676 | 222 |
| mom60 | 2024 | -0.0228 | -0.0817 | 0.4865 | 222 |
| mom60 | 2025 | -0.0894 | -0.4693 | 0.3305 | 118 |
| profit_growth | 2021 | -0.0324 | -0.1533 | 0.4028 | 144 |
| profit_growth | 2022 | -0.0605 | -0.3037 | 0.3964 | 222 |
| profit_growth | 2023 | -0.0606 | -0.4524 | 0.3198 | 222 |
| profit_growth | 2024 | 0.0254 | 0.1438 | 0.5000 | 222 |
| profit_growth | 2025 | 0.0794 | 0.7516 | 0.7712 | 118 |
| revenue_growth | 2021 | -0.0389 | -0.1967 | 0.4097 | 144 |
| revenue_growth | 2022 | -0.0746 | -0.3271 | 0.3874 | 222 |
| revenue_growth | 2023 | -0.0874 | -0.5221 | 0.2568 | 222 |
| revenue_growth | 2024 | -0.0044 | -0.0259 | 0.5315 | 222 |
| revenue_growth | 2025 | 0.0331 | 0.2184 | 0.5593 | 118 |
| reversal_mom3 | 2021 | 0.0058 | 0.0284 | 0.5000 | 144 |
| reversal_mom3 | 2022 | 0.0082 | 0.0389 | 0.4955 | 222 |
| reversal_mom3 | 2023 | -0.0194 | -0.1012 | 0.4505 | 222 |
| reversal_mom3 | 2024 | -0.0004 | -0.0020 | 0.4955 | 222 |
| reversal_mom3 | 2025 | 0.0010 | 0.0042 | 0.3983 | 118 |
| reversal_mom5 | 2021 | 0.0026 | 0.0133 | 0.5069 | 144 |
| reversal_mom5 | 2022 | 0.0155 | 0.0720 | 0.5315 | 222 |
| reversal_mom5 | 2023 | -0.0214 | -0.1047 | 0.4459 | 222 |
| reversal_mom5 | 2024 | 0.0001 | 0.0005 | 0.4640 | 222 |
| reversal_mom5 | 2025 | -0.0024 | -0.0093 | 0.4068 | 118 |
| roe | 2021 | -0.0722 | -0.5003 | 0.3333 | 144 |
| roe | 2022 | -0.0308 | -0.2304 | 0.4054 | 222 |
| roe | 2023 | -0.0454 | -0.2298 | 0.3829 | 222 |
| roe | 2024 | -0.0169 | -0.1097 | 0.5090 | 222 |
| roe | 2025 | 0.0687 | 0.4097 | 0.7627 | 118 |

## Factor Correlation

| factor | low_vol20 | low_vol60 | low_turnover_rate | low_amount_ratio20 | mom20 | mom60 | reversal_mom3 | reversal_mom5 | roe | cash_flow_quality | profit_growth | revenue_growth | low_debt_to_asset | ep | low_pb |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| low_vol20 | 1.0000 | 0.8434 | 0.6275 | -0.0360 | -0.1002 | -0.0828 | -0.0101 | 0.0054 | -0.0265 | 0.1092 | -0.1453 | -0.2257 | -0.2659 | 0.4360 | 0.4440 |
| low_vol60 | 0.8434 | 1.0000 | 0.6488 | -0.0500 | 0.0243 | -0.0012 | -0.0366 | -0.0291 | -0.0286 | 0.1364 | -0.1557 | -0.2641 | -0.3087 | 0.4754 | 0.4884 |
| low_turnover_rate | 0.6275 | 0.6488 | 1.0000 | 0.2624 | -0.0202 | 0.0303 | 0.0341 | 0.0329 | 0.0555 | 0.0848 | -0.1854 | -0.2253 | -0.1968 | 0.3801 | 0.3213 |
| low_amount_ratio20 | -0.0360 | -0.0500 | 0.2624 | 1.0000 | -0.1987 | -0.0627 | 0.2866 | 0.3010 | -0.0269 | -0.0024 | -0.0187 | -0.0166 | 0.0072 | -0.0016 | 0.0170 |
| mom20 | -0.1002 | 0.0243 | -0.0202 | -0.1987 | 1.0000 | 0.4823 | -0.3307 | -0.4402 | -0.0002 | 0.0434 | 0.0133 | -0.0154 | -0.0612 | -0.0100 | -0.0019 |
| mom60 | -0.0828 | -0.0012 | 0.0303 | -0.0627 | 0.4823 | 1.0000 | -0.1779 | -0.2284 | -0.0106 | 0.0610 | 0.0379 | -0.0193 | -0.0895 | -0.0386 | -0.0242 |
| reversal_mom3 | -0.0101 | -0.0366 | 0.0341 | 0.2866 | -0.3307 | -0.1779 | 1.0000 | 0.7230 | 0.0050 | -0.0224 | 0.0017 | 0.0152 | 0.0356 | -0.0091 | -0.0131 |
| reversal_mom5 | 0.0054 | -0.0291 | 0.0329 | 0.3010 | -0.4402 | -0.2284 | 0.7230 | 1.0000 | 0.0035 | -0.0250 | -0.0010 | 0.0146 | 0.0395 | -0.0042 | -0.0086 |
| roe | -0.0265 | -0.0286 | 0.0555 | -0.0269 | -0.0002 | -0.0106 | 0.0050 | 0.0035 | 1.0000 | -0.0588 | 0.4147 | 0.3512 | 0.2298 | 0.1529 | -0.3436 |
| cash_flow_quality | 0.1092 | 0.1364 | 0.0848 | -0.0024 | 0.0434 | 0.0610 | -0.0224 | -0.0250 | -0.0588 | 1.0000 | -0.0083 | -0.0503 | -0.1197 | 0.0476 | 0.1448 |
| profit_growth | -0.1453 | -0.1557 | -0.1854 | -0.0187 | 0.0133 | 0.0379 | 0.0017 | -0.0010 | 0.4147 | -0.0083 | 1.0000 | 0.6207 | 0.1033 | -0.1061 | -0.2678 |
| revenue_growth | -0.2257 | -0.2641 | -0.2253 | -0.0166 | -0.0154 | -0.0193 | 0.0152 | 0.0146 | 0.3512 | -0.0503 | 0.6207 | 1.0000 | 0.1629 | -0.2198 | -0.3645 |
| low_debt_to_asset | -0.2659 | -0.3087 | -0.1968 | 0.0072 | -0.0612 | -0.0895 | 0.0356 | 0.0395 | 0.2298 | -0.1197 | 0.1033 | 0.1629 | 1.0000 | -0.4618 | -0.5489 |
| ep | 0.4360 | 0.4754 | 0.3801 | -0.0016 | -0.0100 | -0.0386 | -0.0091 | -0.0042 | 0.1529 | 0.0476 | -0.1061 | -0.2198 | -0.4618 | 1.0000 | 0.7494 |
| low_pb | 0.4440 | 0.4884 | 0.3213 | 0.0170 | -0.0019 | -0.0242 | -0.0131 | -0.0086 | -0.3436 | 0.1448 | -0.2678 | -0.3645 | -0.5489 | 0.7494 | 1.0000 |

## Warnings / Data Coverage

- No material warning generated by this diagnostic run.
