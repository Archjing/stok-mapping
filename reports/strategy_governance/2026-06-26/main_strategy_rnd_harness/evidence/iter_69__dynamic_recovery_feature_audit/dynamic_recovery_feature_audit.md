# Dynamic Recovery Feature Audit

Research-only I69 audit. Forward returns are post-hoc labels for feature discovery only.

## Fold Summary

|   fold |   recovery_days |   positive_forward_20d_ratio |   avg_forward_20d_return |   tradable_days |   avg_breadth20 |   avg_industry_breadth |   avg_amount_ratio |   avg_breadth20_delta_20d |   avg_industry_breadth_delta_20d |   avg_amount_delta_20d |   avg_leader_persistence_20d |
|-------:|----------------:|-----------------------------:|-------------------------:|----------------:|----------------:|-----------------------:|-------------------:|--------------------------:|---------------------------------:|-----------------------:|-----------------------------:|
|      2 |              56 |                     0.125    |               -0.0265661 |              28 |        0.636911 |               0.640192 |           1.05901  |                 0.0465951 |                        0.021322  |              0.0383491 |                    0         |
|      3 |              22 |                     0        |               -0.0237883 |               6 |        0.658941 |               0.661096 |           0.987627 |                 0.108293  |                        0.0974265 |             -0.260754  |                    0.181818  |
|      4 |              49 |                     0.326531 |               -0.0127058 |               8 |        0.515699 |               0.557417 |           0.98967  |                 0.125586  |                        0.0755597 |              0.0375756 |                    0.0204082 |
|      5 |              46 |                     0.978261 |                0.0499201 |              36 |        0.759249 |               0.759761 |           1.17578  |                 0.0811509 |                        0.10037   |              0.0334388 |                    0.891304  |

## Good vs Bad Recovery Labels

| positive_forward_20d   |   days |   avg_forward_20d_return |   tradable_ratio |   avg_breadth20 |   avg_breadth60 |   avg_industry_breadth |   avg_amount_ratio |   avg_breadth20_delta_20d |   avg_industry_breadth_delta_20d |   avg_amount_delta_20d |   avg_leader_persistence_20d |
|:-----------------------|-------:|-------------------------:|-----------------:|----------------:|----------------:|-----------------------:|-------------------:|--------------------------:|---------------------------------:|-----------------------:|-----------------------------:|
| False                  |    105 |               -0.0327017 |         0.371429 |        0.629561 |        0.693356 |               0.64214  |            1.00445 |                 0.0886355 |                        0.064572  |             -0.0369255 |                     0.047619 |
| True                   |     68 |                0.0428061 |         0.573529 |        0.650801 |        0.746368 |               0.665185 |            1.14919 |                 0.0659635 |                        0.0664959 |              0.0810917 |                     0.602941 |

## Fold2 vs Fold5 Contrast

|   fold |   positive_forward_20d_ratio |   avg_forward_20d_return |   avg_breadth20 |   avg_industry_breadth |   avg_amount_ratio |   avg_breadth20_delta_20d |   avg_industry_breadth_delta_20d |   avg_amount_delta_20d |   avg_leader_persistence_20d |
|-------:|-----------------------------:|-------------------------:|----------------:|-----------------------:|-------------------:|--------------------------:|---------------------------------:|-----------------------:|-----------------------------:|
|      2 |                     0.125    |               -0.0265661 |        0.636911 |               0.640192 |            1.05901 |                 0.0465951 |                         0.021322 |              0.0383491 |                     0        |
|      5 |                     0.978261 |                0.0499201 |        0.759249 |               0.759761 |            1.17578 |                 0.0811509 |                         0.10037  |              0.0334388 |                     0.891304 |

## Plain Conclusion

- Fold5 true recovery has much higher positive-forward ratio than fold2.
- Static breadth levels are similar enough that they cannot alone separate false and true recovery.
- Dynamic breadth/amount deltas show candidate signals for follow-up, but this audit is not yet a validated classifier.
- The immediate engineering win is improved holdings-exposure observability: signal diagnostics now include momentum, amount, volatility, and recovery breadth fields.

## Data Safety Note

Breadth features in the strategy signal are pre-shifted by the strategy preparation path. Forward returns and future-window diagnostics such as `leader_persistence_20d` are audit-only labels/explanations and must not be used as live inputs. Any follow-up strategy must use only features visible no later than T-1.
