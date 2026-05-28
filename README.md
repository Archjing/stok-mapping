# stok-mapping

`Phase 0` implementation for:

- Data-source connectivity checks (`yfinance`, `akshare`)
- Data-quality audit (`OHLCV` integrity, missing ratio, delay check)
- Walk-forward backtest baseline (daily data)
- Sample out-of-sample split summary

## Run

This project intentionally reuses the existing `stok-quant` virtual environment to avoid duplicate setup.

```bash
/home/zj/workspace/stok-quant/.venv/bin/python -m phase0.cli run
```

## Output

- `reports/phase0_data_source_report.md`
- `reports/phase0_walk_forward_report.md`
- `reports/phase0_effectiveness_report.md`
