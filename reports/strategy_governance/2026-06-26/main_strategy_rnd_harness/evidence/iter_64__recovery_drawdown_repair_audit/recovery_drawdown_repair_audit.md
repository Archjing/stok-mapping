# Recovery Drawdown Repair Audit

Research-only audit for I64. Uses I63 daily exposure output and computes whether `strong_index_drawdown` improved versus 20 trading days earlier.

## Fold Summary

|   fold |   recovery_days |   repair_days |   non_repair_days |   repair_benchmark_return_sum |   non_repair_benchmark_return_sum |   repair_benchmark_return_mean |   non_repair_benchmark_return_mean |
|-------:|----------------:|--------------:|------------------:|------------------------------:|----------------------------------:|-------------------------------:|-----------------------------------:|
|      2 |              56 |            43 |                13 |                     -0.039348 |                         -0.002201 |                      -0.000915 |                          -0.000169 |
|      3 |              22 |            16 |                 6 |                      0.00256  |                          0.012162 |                       0.00016  |                           0.002027 |
|      4 |              49 |            26 |                23 |                     -0.003872 |                         -0.018184 |                      -0.000149 |                          -0.000791 |
|      5 |              46 |            46 |                 0 |                      0.143221 |                          0        |                       0.003113 |                           0        |

## Bucket Summary

|   fold | drawdown_repair_bucket   |   days |   benchmark_return_sum |   benchmark_return_mean |   avg_drawdown_delta_20d |   quality_days |   avg_target_exposure |
|-------:|:-------------------------|-------:|-----------------------:|------------------------:|-------------------------:|---------------:|----------------------:|
|      2 | flat_or_unknown          |     13 |              -0.002201 |               -0.000169 |                -0.008072 |              0 |              0.342308 |
|      2 | mild_repair              |     28 |              -0.049386 |               -0.001764 |                 0.021375 |             20 |              0.471429 |
|      2 | strong_repair            |     15 |               0.010038 |                0.000669 |                 0.061207 |             14 |              0.35     |
|      3 | flat_or_unknown          |      6 |               0.012162 |                0.002027 |                 0        |              2 |              0.4      |
|      3 | mild_repair              |     12 |              -0.009562 |               -0.000797 |                 0.021635 |              9 |              0.191667 |
|      3 | strong_repair            |      4 |               0.012122 |                0.00303  |                 0.062342 |              0 |              0.15     |
|      4 | flat_or_unknown          |     23 |              -0.018184 |               -0.000791 |                -0.00654  |              2 |              0.334783 |
|      4 | mild_repair              |     26 |              -0.003872 |               -0.000149 |                 0.018379 |             15 |              0.390338 |
|      5 | mild_repair              |     38 |               0.155931 |                0.004103 |                 0.030107 |             37 |              0.437549 |
|      5 | strong_repair            |      8 |              -0.01271  |               -0.001589 |                 0.064669 |              4 |              0.647898 |
