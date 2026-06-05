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
| low_pb | 1.0000 | 0.0955 | 0.3878 | 0.6390 | 0.0153 | 2.0049 | use | positive IC and positive top-bottom return |
| low_vol60 | 0.7455 | 0.0951 | 0.3195 | 0.6214 | 0.0100 | 8.9957 | use | positive IC and positive top-bottom return |
| low_turnover_rate | 1.0000 | 0.0840 | 0.2992 | 0.6207 | 0.0035 | 49.7136 | use | positive IC and positive top-bottom return |
| low_vol20 | 1.0000 | 0.0829 | 0.3089 | 0.6379 | 0.0056 | 21.1133 | use | positive IC and positive top-bottom return |
| ep | 0.9537 | 0.0788 | 0.2769 | 0.5959 | 0.0070 | 3.5867 | use | positive IC and positive top-bottom return |
| cash_flow_quality | 0.9959 | 0.0577 | 0.5150 | 0.7015 | 0.0083 | 2.2201 | use | positive IC and positive top-bottom return |
| reversal_mom3 | 1.0000 | -0.0021 | -0.0099 | 0.4774 | 0.0004 | 116.3948 | observe | weak but non-negative IC or top-bottom return |
| profit_growth | 0.9959 | -0.0200 | -0.1147 | 0.4591 | 0.0014 | 2.1634 | observe | weak but non-negative IC or top-bottom return |
| reversal_mom5 | 1.0000 | -0.0016 | -0.0074 | 0.4774 | -0.0002 | 91.4644 | reject | negative IC and no positive top-bottom return |
| low_amount_ratio20 | 1.0000 | -0.0089 | -0.0546 | 0.4634 | -0.0023 | 134.2006 | reject | negative IC and no positive top-bottom return |
| roe | 0.9959 | -0.0304 | -0.1844 | 0.4375 | -0.0131 | 3.9984 | reject | negative IC and no positive top-bottom return |
| mom20 | 1.0000 | -0.0357 | -0.1591 | 0.4892 | -0.0078 | 44.2087 | reject | negative IC and no positive top-bottom return |
| revenue_growth | 0.9959 | -0.0493 | -0.2631 | 0.3976 | -0.0073 | 1.8803 | reject | negative IC and no positive top-bottom return |
| mom60 | 1.0000 | -0.0502 | -0.2176 | 0.4321 | -0.0098 | 26.1990 | reject | negative IC and no positive top-bottom return |
| low_debt_to_asset | 0.9959 | -0.0648 | -0.3451 | 0.3772 | -0.0127 | 0.8382 | reject | negative IC and no positive top-bottom return |

## Group Returns Summary

| factor | group | mean_forward_return | sample_count |
| --- | --- | --- | --- |
| cash_flow_quality | 1 | -0.0049 | 21765 |
| cash_flow_quality | 2 | -0.0085 | 22262 |
| cash_flow_quality | 3 | -0.0075 | 22249 |
| cash_flow_quality | 4 | 0.0016 | 22262 |
| cash_flow_quality | 5 | 0.0035 | 22272 |
| ep | 1 | -0.0037 | 20913 |
| ep | 2 | -0.0072 | 21144 |
| ep | 3 | -0.0052 | 21342 |
| ep | 4 | -0.0037 | 21144 |
| ep | 5 | 0.0033 | 21568 |
| low_amount_ratio20 | 1 | -0.0019 | 22204 |
| low_amount_ratio20 | 2 | -0.0028 | 22272 |
| low_amount_ratio20 | 3 | -0.0026 | 22244 |
| low_amount_ratio20 | 4 | -0.0043 | 22272 |
| low_amount_ratio20 | 5 | -0.0042 | 22272 |
| low_debt_to_asset | 1 | 0.0054 | 21765 |
| low_debt_to_asset | 2 | -0.0048 | 22262 |
| low_debt_to_asset | 3 | -0.0017 | 22249 |
| low_debt_to_asset | 4 | -0.0071 | 22262 |
| low_debt_to_asset | 5 | -0.0073 | 22272 |
| low_pb | 1 | -0.0092 | 22204 |
| low_pb | 2 | -0.0038 | 22272 |
| low_pb | 3 | -0.0062 | 22244 |
| low_pb | 4 | -0.0025 | 22272 |
| low_pb | 5 | 0.0060 | 22272 |
| low_turnover_rate | 1 | -0.0023 | 22204 |
| low_turnover_rate | 2 | -0.0055 | 22272 |
| low_turnover_rate | 3 | -0.0074 | 22244 |
| low_turnover_rate | 4 | -0.0017 | 22272 |
| low_turnover_rate | 5 | 0.0012 | 22272 |
| low_vol20 | 1 | -0.0027 | 22204 |
| low_vol20 | 2 | -0.0053 | 22272 |
| low_vol20 | 3 | -0.0057 | 22244 |
| low_vol20 | 4 | -0.0049 | 22272 |
| low_vol20 | 5 | 0.0029 | 22272 |
| low_vol60 | 1 | -0.0068 | 16541 |
| low_vol60 | 2 | -0.0147 | 16607 |
| low_vol60 | 3 | -0.0041 | 16581 |
| low_vol60 | 4 | -0.0054 | 16607 |
| low_vol60 | 5 | 0.0032 | 16608 |
| mom20 | 1 | -0.0001 | 22204 |
| mom20 | 2 | -0.0019 | 22272 |
| mom20 | 3 | -0.0018 | 22244 |
| mom20 | 4 | -0.0042 | 22272 |
| mom20 | 5 | -0.0079 | 22272 |
| mom60 | 1 | 0.0013 | 22204 |
| mom60 | 2 | -0.0010 | 22272 |
| mom60 | 3 | -0.0022 | 22244 |
| mom60 | 4 | -0.0054 | 22272 |
| mom60 | 5 | -0.0085 | 22272 |
| profit_growth | 1 | -0.0065 | 21765 |
| profit_growth | 2 | 0.0000 | 22262 |
| profit_growth | 3 | -0.0028 | 22249 |
| profit_growth | 4 | -0.0015 | 22262 |
| profit_growth | 5 | -0.0051 | 22272 |
| revenue_growth | 1 | 0.0009 | 21765 |
| revenue_growth | 2 | -0.0016 | 22262 |
| revenue_growth | 3 | -0.0035 | 22249 |
| revenue_growth | 4 | -0.0052 | 22262 |
| revenue_growth | 5 | -0.0064 | 22272 |
| reversal_mom3 | 1 | -0.0043 | 22204 |
| reversal_mom3 | 2 | -0.0022 | 22272 |
| reversal_mom3 | 3 | -0.0024 | 22244 |
| reversal_mom3 | 4 | -0.0028 | 22272 |
| reversal_mom3 | 5 | -0.0039 | 22272 |
| reversal_mom5 | 1 | -0.0046 | 22204 |
| reversal_mom5 | 2 | -0.0025 | 22272 |
| reversal_mom5 | 3 | -0.0017 | 22244 |
| reversal_mom5 | 4 | -0.0022 | 22272 |
| reversal_mom5 | 5 | -0.0048 | 22272 |
| roe | 1 | -0.0011 | 21765 |
| roe | 2 | 0.0024 | 22262 |
| roe | 3 | -0.0020 | 22249 |
| roe | 4 | -0.0007 | 22262 |
| roe | 5 | -0.0143 | 22272 |

## Yearly IC Summary

| factor | year | mean_rank_ic | icir | positive_ic_ratio | sample_days |
| --- | --- | --- | --- | --- | --- |
| cash_flow_quality | 2021 | 0.0067 | 0.0802 | 0.5931 | 145 |
| cash_flow_quality | 2022 | 0.0317 | 0.3383 | 0.6441 | 222 |
| cash_flow_quality | 2023 | 0.1158 | 1.0354 | 0.8153 | 222 |
| cash_flow_quality | 2024 | 0.0638 | 0.5177 | 0.7027 | 222 |
| cash_flow_quality | 2025 | 0.0481 | 0.4609 | 0.7265 | 117 |
| ep | 2021 | 0.0888 | 0.2671 | 0.5586 | 145 |
| ep | 2022 | 0.0673 | 0.2449 | 0.5450 | 222 |
| ep | 2023 | 0.1138 | 0.4430 | 0.6171 | 222 |
| ep | 2024 | 0.0218 | 0.0761 | 0.5766 | 222 |
| ep | 2025 | 0.1300 | 0.4825 | 0.7350 | 117 |
| low_amount_ratio20 | 2021 | -0.0401 | -0.2597 | 0.3862 | 145 |
| low_amount_ratio20 | 2022 | -0.0001 | -0.0004 | 0.4910 | 222 |
| low_amount_ratio20 | 2023 | -0.0034 | -0.0212 | 0.4820 | 222 |
| low_amount_ratio20 | 2024 | -0.0074 | -0.0430 | 0.4730 | 222 |
| low_amount_ratio20 | 2025 | 0.0001 | 0.0007 | 0.4530 | 117 |
| low_debt_to_asset | 2021 | -0.0965 | -0.4868 | 0.3586 | 145 |
| low_debt_to_asset | 2022 | -0.0344 | -0.2052 | 0.4865 | 222 |
| low_debt_to_asset | 2023 | -0.0733 | -0.3477 | 0.3964 | 222 |
| low_debt_to_asset | 2024 | -0.0622 | -0.3117 | 0.3063 | 222 |
| low_debt_to_asset | 2025 | -0.0717 | -0.5781 | 0.2906 | 117 |
| low_pb | 2021 | 0.1182 | 0.3958 | 0.5931 | 145 |
| low_pb | 2022 | 0.0982 | 0.3998 | 0.6171 | 222 |
| low_pb | 2023 | 0.1589 | 0.7329 | 0.7523 | 222 |
| low_pb | 2024 | 0.0328 | 0.1337 | 0.5991 | 222 |
| low_pb | 2025 | 0.0605 | 0.3132 | 0.5983 | 117 |
| low_turnover_rate | 2021 | 0.0479 | 0.1837 | 0.5310 | 145 |
| low_turnover_rate | 2022 | 0.1033 | 0.4060 | 0.6532 | 222 |
| low_turnover_rate | 2023 | 0.1671 | 0.7185 | 0.7703 | 222 |
| low_turnover_rate | 2024 | 0.0414 | 0.1247 | 0.5766 | 222 |
| low_turnover_rate | 2025 | 0.0155 | 0.0531 | 0.4701 | 117 |
| low_vol20 | 2021 | 0.0879 | 0.3811 | 0.6897 | 145 |
| low_vol20 | 2022 | 0.0432 | 0.1927 | 0.5856 | 222 |
| low_vol20 | 2023 | 0.1685 | 0.7681 | 0.7523 | 222 |
| low_vol20 | 2024 | 0.0811 | 0.2662 | 0.6622 | 222 |
| low_vol20 | 2025 | -0.0072 | -0.0209 | 0.4103 | 117 |
| low_vol60 | 2021 | 0.1669 | 0.8104 | 0.7442 | 86 |
| low_vol60 | 2022 | 0.0440 | 0.1649 | 0.5153 | 163 |
| low_vol60 | 2023 | 0.1383 | 0.5789 | 0.7055 | 163 |
| low_vol60 | 2024 | 0.1262 | 0.3761 | 0.7178 | 163 |
| low_vol60 | 2025 | 0.0101 | 0.0269 | 0.4274 | 117 |
| mom20 | 2021 | -0.0197 | -0.0820 | 0.5241 | 145 |
| mom20 | 2022 | -0.0778 | -0.3535 | 0.3964 | 222 |
| mom20 | 2023 | -0.0168 | -0.0950 | 0.5360 | 222 |
| mom20 | 2024 | -0.0074 | -0.0306 | 0.5090 | 222 |
| mom20 | 2025 | -0.0654 | -0.2621 | 0.4957 | 117 |
| mom60 | 2021 | -0.0795 | -0.3223 | 0.3724 | 145 |
| mom60 | 2022 | -0.0906 | -0.4208 | 0.3559 | 222 |
| mom60 | 2023 | 0.0031 | 0.0166 | 0.5495 | 222 |
| mom60 | 2024 | -0.0238 | -0.0856 | 0.4820 | 222 |
| mom60 | 2025 | -0.0887 | -0.4637 | 0.3333 | 117 |
| profit_growth | 2021 | -0.0372 | -0.1785 | 0.4138 | 145 |
| profit_growth | 2022 | -0.0585 | -0.3040 | 0.4009 | 222 |
| profit_growth | 2023 | -0.0573 | -0.4289 | 0.3063 | 222 |
| profit_growth | 2024 | 0.0151 | 0.0887 | 0.5360 | 222 |
| profit_growth | 2025 | 0.0787 | 0.7439 | 0.7692 | 117 |
| revenue_growth | 2021 | -0.0661 | -0.3544 | 0.3379 | 145 |
| revenue_growth | 2022 | -0.0686 | -0.2998 | 0.4009 | 222 |
| revenue_growth | 2023 | -0.0860 | -0.5137 | 0.2658 | 222 |
| revenue_growth | 2024 | -0.0248 | -0.1522 | 0.4820 | 222 |
| revenue_growth | 2025 | 0.0311 | 0.2066 | 0.5556 | 117 |
| reversal_mom3 | 2021 | 0.0030 | 0.0148 | 0.5034 | 145 |
| reversal_mom3 | 2022 | 0.0066 | 0.0309 | 0.5180 | 222 |
| reversal_mom3 | 2023 | -0.0176 | -0.0912 | 0.4369 | 222 |
| reversal_mom3 | 2024 | -0.0018 | -0.0080 | 0.5000 | 222 |
| reversal_mom3 | 2025 | 0.0038 | 0.0158 | 0.4017 | 117 |
| reversal_mom5 | 2021 | -0.0021 | -0.0111 | 0.5103 | 145 |
| reversal_mom5 | 2022 | 0.0146 | 0.0671 | 0.5225 | 222 |
| reversal_mom5 | 2023 | -0.0190 | -0.0934 | 0.4459 | 222 |
| reversal_mom5 | 2024 | -0.0012 | -0.0052 | 0.4775 | 222 |
| reversal_mom5 | 2025 | 0.0003 | 0.0012 | 0.4103 | 117 |
| roe | 2021 | -0.0740 | -0.5373 | 0.3103 | 145 |
| roe | 2022 | -0.0338 | -0.2669 | 0.4144 | 222 |
| roe | 2023 | -0.0438 | -0.2219 | 0.3829 | 222 |
| roe | 2024 | -0.0372 | -0.2361 | 0.4279 | 222 |
| roe | 2025 | 0.0687 | 0.4082 | 0.7607 | 117 |

## Factor Correlation

| factor | low_vol20 | low_vol60 | low_turnover_rate | low_amount_ratio20 | mom20 | mom60 | reversal_mom3 | reversal_mom5 | roe | cash_flow_quality | profit_growth | revenue_growth | low_debt_to_asset | ep | low_pb |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| low_vol20 | 1.0000 | 0.8442 | 0.6304 | -0.0363 | -0.0987 | -0.0843 | -0.0102 | 0.0050 | -0.0291 | 0.1142 | -0.1497 | -0.2312 | -0.2703 | 0.4408 | 0.4468 |
| low_vol60 | 0.8442 | 1.0000 | 0.6516 | -0.0504 | 0.0258 | -0.0010 | -0.0368 | -0.0305 | -0.0348 | 0.1427 | -0.1594 | -0.2633 | -0.3140 | 0.4803 | 0.4912 |
| low_turnover_rate | 0.6304 | 0.6516 | 1.0000 | 0.2610 | -0.0218 | 0.0268 | 0.0341 | 0.0331 | 0.0554 | 0.0886 | -0.1850 | -0.2229 | -0.1965 | 0.3874 | 0.3253 |
| low_amount_ratio20 | -0.0363 | -0.0504 | 0.2610 | 1.0000 | -0.1979 | -0.0624 | 0.2849 | 0.2994 | -0.0247 | -0.0050 | -0.0163 | -0.0154 | 0.0079 | -0.0024 | 0.0161 |
| mom20 | -0.0987 | 0.0258 | -0.0218 | -0.1979 | 1.0000 | 0.4828 | -0.3308 | -0.4405 | -0.0075 | 0.0469 | 0.0077 | -0.0214 | -0.0607 | -0.0094 | -0.0017 |
| mom60 | -0.0843 | -0.0010 | 0.0268 | -0.0624 | 0.4828 | 1.0000 | -0.1778 | -0.2283 | -0.0248 | 0.0640 | 0.0326 | -0.0222 | -0.0872 | -0.0376 | -0.0244 |
| reversal_mom3 | -0.0102 | -0.0368 | 0.0341 | 0.2849 | -0.3308 | -0.1778 | 1.0000 | 0.7230 | 0.0093 | -0.0242 | 0.0035 | 0.0181 | 0.0358 | -0.0096 | -0.0135 |
| reversal_mom5 | 0.0050 | -0.0305 | 0.0331 | 0.2994 | -0.4405 | -0.2283 | 0.7230 | 1.0000 | 0.0080 | -0.0273 | 0.0010 | 0.0176 | 0.0399 | -0.0052 | -0.0094 |
| roe | -0.0291 | -0.0348 | 0.0554 | -0.0247 | -0.0075 | -0.0248 | 0.0093 | 0.0080 | 1.0000 | -0.0578 | 0.4058 | 0.3659 | 0.2218 | 0.1446 | -0.3404 |
| cash_flow_quality | 0.1142 | 0.1427 | 0.0886 | -0.0050 | 0.0469 | 0.0640 | -0.0242 | -0.0273 | -0.0578 | 1.0000 | 0.0047 | -0.0415 | -0.1272 | 0.0591 | 0.1537 |
| profit_growth | -0.1497 | -0.1594 | -0.1850 | -0.0163 | 0.0077 | 0.0326 | 0.0035 | 0.0010 | 0.4058 | 0.0047 | 1.0000 | 0.6147 | 0.1034 | -0.1236 | -0.2725 |
| revenue_growth | -0.2312 | -0.2633 | -0.2229 | -0.0154 | -0.0214 | -0.0222 | 0.0181 | 0.0176 | 0.3659 | -0.0415 | 0.6147 | 1.0000 | 0.1735 | -0.2336 | -0.3799 |
| low_debt_to_asset | -0.2703 | -0.3140 | -0.1965 | 0.0079 | -0.0607 | -0.0872 | 0.0358 | 0.0399 | 0.2218 | -0.1272 | 0.1034 | 0.1735 | 1.0000 | -0.4759 | -0.5553 |
| ep | 0.4408 | 0.4803 | 0.3874 | -0.0024 | -0.0094 | -0.0376 | -0.0096 | -0.0052 | 0.1446 | 0.0591 | -0.1236 | -0.2336 | -0.4759 | 1.0000 | 0.7529 |
| low_pb | 0.4468 | 0.4912 | 0.3253 | 0.0161 | -0.0017 | -0.0244 | -0.0135 | -0.0094 | -0.3404 | 0.1537 | -0.2725 | -0.3799 | -0.5553 | 0.7529 | 1.0000 |

## Warnings / Data Coverage

- No material warning generated by this diagnostic run.
