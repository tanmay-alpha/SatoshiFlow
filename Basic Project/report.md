# SatoshiFlow verified report

> **PROVISIONAL:** The official `BTC_2019_2023_1d.csv` file is missing.

## Dataset

- File: `btc_18_22_1d.csv`
- Range: 2018-01-01 to 2022-12-31
- SHA-256: `32814cd9f3b83dc79a0092c1f1c24bd988dad4c4b230dcd421401025ac660748`
- Evaluation: 2022 provisional out-of-sample

## Strategy

30-day shifted Donchian breakout, ADX >= 20, DI direction confirmation,
200-day EMA regime filter, and 2.5 x ATR trailing stop. Decisions formed on
bar t execute at bar t+1 open.

## Verified metrics

| Metric | Value |
|---|---:|
| Final equity | $1,210.46 |
| Net return | 21.05% |
| Sharpe ratio | 0.709383 |
| Maximum drawdown | 22.51% |
| Win rate | 50.0000% |
| Total trades | 6 |
| Total brokerage | $20.42 |
| Buy-and-hold return | -64.21% |

## Integrity

- LOOKAHEAD CHECK: PASS
- NEXT-BAR EXECUTION CHECK: PASS
- REPRODUCIBILITY CHECK: PASS

The PDF and this file are generated from `results/metrics.json`.
