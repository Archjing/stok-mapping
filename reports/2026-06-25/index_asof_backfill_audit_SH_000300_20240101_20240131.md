# CSI300 Index As-Of Backfill Audit

- generated_at: `2026-06-25T09:17:39`
- task: `CSI300 historical constituents and weights as-of data backfill`
- status: `ok`
- db_path: `/home/zj/workspace/stok-mapping/data/manual_history/a_share_history.sqlite`
- index_code: `SH.000300`
- vendor_index_code: `000300.SH`
- source: `tushare.index_weight`
- date_range: `2024-01-01..2024-01-31`
- fetched_rows: `600`
- inserted_weight_rows: `600`
- inserted_constituent_rows: `600`
- distinct_trade_dates: `2`
- actual_trade_date_span: `2024-01-02..2024-01-31`
- weights_table: `cn_index_weights_asof`
- constituents_table: `cn_index_constituents_asof`

## As-Of 口径

- `trade_date` / `effective_date` 表示指数权重生效日。
- `asof_time` 当前写为 `trade_date T18:00:00`，表示收盘后可见代理时间；不得解释为盘中可见数据。
- `cn_index_constituents_asof` 由同一批权重记录派生，避免成分和权重日期口径不一致。
