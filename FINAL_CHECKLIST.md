# Final submission checklist

- [ ] Official `BTC_2019_2023_1d.csv` dataset used
- [x] Exact initial capital is $1,000
- [x] Exact brokerage is 0.15% on entry and exit
- [x] No lookahead (prefix and indicator invariance)
- [x] Next-bar-open execution
- [x] Final position closed
- [x] Metrics reproduced twice
- [x] PDF metrics match `results/metrics.json`
- [x] README command tested
- [x] `SUBMIT_THESE/` contains only required files

## External blocker

The official `BTC_2019_2023_1d.csv` dataset is absent. The verified snapshot
uses `btc_18_22_1d.csv` and labels 2022 results provisional. Re-run `main.py`
and `generate_report.py` with the official file before external submission.
