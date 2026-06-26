# Negative Recovery Classifier Audit

Research-only I68 audit. Forward returns are post-hoc labels for diagnosis, not strategy inputs.

## Fold Summary

|   fold |   recovery_days |   tradable_days |   benchmark_return_sum |   avg_forward_5d_return |   avg_forward_20d_return |   positive_forward_20d_ratio |   avg_ret20 |   avg_ret60 |   avg_drawdown |   avg_vol_ratio |   avg_live_exposure |   avg_target_exposure |   avg_industry_l1_gap_norm |   avg_max_abs_norm_active |   tradable_ratio_of_recovery |
|-------:|----------------:|----------------:|-----------------------:|------------------------:|-------------------------:|-----------------------------:|------------:|------------:|---------------:|----------------:|--------------------:|----------------------:|---------------------------:|--------------------------:|-----------------------------:|
|      2 |              56 |              28 |             -0.0415494 |             -0.00423965 |               -0.0265661 |                     0.125    |   0.036815  |   0.0793548 |      -0.27947  |        0.709314 |            0.385714 |              0.407143 |                   0.386083 |                 0.0527655 |                     0.5      |
|      3 |              22 |               6 |              0.0147222 |             -0.00311714 |               -0.0237883 |                     0        |   0.0437366 |   0.0556927 |      -0.361969 |        0.848085 |            0.188636 |              0.213636 |                   0.376095 |                 0.0491602 |                     0.272727 |
|      4 |              49 |               8 |             -0.0220566 |             -0.00221579 |               -0.0127058 |                     0.326531 |   0.0145315 |   0.111068  |      -0.363488 |        0.919439 |            0.297934 |              0.309159 |                   0.374525 |                 0.0433323 |                     0.163265 |
|      5 |              46 |              36 |              0.143221  |              0.0143832  |                0.0499201 |                     0.978261 |   0.0456974 |   0.0933672 |      -0.177261 |        0.592994 |            0.463262 |              0.474131 |                   0.379656 |                 0.0588861 |                     0.782609 |

## Outcome Summary

|   fold | recovery_outcome_20d   |   days |   tradable_days |   avg_forward_20d_return |   avg_ret20 |   avg_ret60 |   avg_drawdown |   avg_vol_ratio |   avg_industry_l1_gap_norm |   tradable_ratio |
|-------:|:-----------------------|-------:|----------------:|-------------------------:|------------:|------------:|---------------:|----------------:|---------------------------:|-----------------:|
|      2 | negative_forward_20d   |     49 |              26 |              -0.0345682  |  0.0387148  |   0.0808128 |      -0.275876 |        0.719069 |                   0.385267 |         0.530612 |
|      2 | positive_forward_20d   |      7 |               2 |               0.0214465  |  0.0235164  |   0.0691486 |      -0.304628 |        0.641031 |                   0.391795 |         0.285714 |
|      3 | negative_forward_20d   |     22 |               6 |              -0.0237883  |  0.0437366  |   0.0556927 |      -0.361969 |        0.848085 |                   0.376095 |         0.272727 |
|      4 | negative_forward_20d   |     33 |               7 |              -0.0327125  |  0.0217888  |   0.132216  |      -0.353045 |        0.926956 |                   0.368025 |         0.212121 |
|      4 | positive_forward_20d   |     16 |               1 |               0.0285582  | -0.00043676 |   0.0674507 |      -0.385024 |        0.903933 |                   0.388827 |         0.0625   |
|      5 | negative_forward_20d   |      1 |               0 |              -0.00743179 |  0.0643541  |   0.147199  |      -0.125583 |        1.02706  |                   0.396918 |         0        |
|      5 | positive_forward_20d   |     45 |              36 |               0.0511946  |  0.0452828  |   0.0921709 |      -0.178409 |        0.583348 |                   0.379272 |         0.8      |

## Leadership Modes

|   fold | top_overweight_industry   |   days |   tradable_days |   avg_forward_20d_return |   avg_benchmark_return_sum |
|-------:|:--------------------------|-------:|----------------:|-------------------------:|---------------------------:|
|      2 | 白酒                        |     56 |              28 |              -0.0265661  |                -0.0415494  |
|      3 | 白酒                        |     21 |               6 |              -0.024943   |                 0.00493684 |
|      4 | 白酒                        |     35 |               6 |              -0.00553111 |                -0.0119082  |
|      4 | 银行                        |     13 |               2 |              -0.0343308  |                -0.0265923  |
|      5 | 银行                        |     46 |              36 |               0.0499201  |                 0.143221   |

## Plain Conclusion

- Fold2 remains the clearest false recovery case: I67 kept 28 of 56 recovery days, but fold-level strategy performance barely improved.
- Fold4 is the clearest partial success: I67 kept only 8 of 49 recovery days and improved annualized return versus I63.
- Fold5 is the true positive recovery case: I67 kept 36 of 46 recovery days and performance stayed unchanged from I63.
- The available pre-visible index features are not enough by themselves. The next useful classifier should test leadership persistence and recovery breadth trend, not only static breadth level.

## Data Safety Note

Forward 5/20 day benchmark returns are used only to label good/bad recovery windows after the fact. They must not be used directly in a live strategy.
