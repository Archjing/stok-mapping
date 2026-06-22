# Strategy Intelligence Monthly Scan Index

| Scan ID | Report | Window | Scope | Candidate Inbox | Ledger Status | Review Status | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `2026-06-a-share` | `strategy_intelligence_scan_2026-06_a_share.md` | `2026-05-11` to `2026-06-10` | A 股策略情报 | `data/intelligence/inbox/a_share_strategy_intelligence_candidates_2026-06-10.csv` | 未自动入账 | 已完成初筛，仍需逐条人工评分后入账 | 本次月扫已筛出高价值策略/数据线索，但不绕过 T5.2 门禁 |

## 维护规则

- 每新增一次月扫，追加一行并同步 `knowledge/intelligence/wiki/log.md`。
- `Ledger Status` 只能写清：未入账、部分入账、已入账、已归档。
- `Review Status` 必须区分自动采集、人工初筛、人工评分、转任务、归档。
- 若条目进入正式台账，必须在 `strategy_intelligence_ledger.csv` 中保留 source 和 reviewed date。
