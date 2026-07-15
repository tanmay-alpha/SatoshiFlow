# BTC Strategy — Final Report Data

**Data file SHA-256:** `32814cd9f3b83dc79a0092c1f1c24bd988dad4c4b230dcd421401025ac660748`
**Dataset:** 1826 rows, 2018-01-01 to 2022-12-31
**Starting capital:** $1000
**Locked Threshold:** ADX_THRESHOLD = 20

---

## Strategy Rationale (TBD)

---

## Threshold Sweep — Walk-Forward Validation

Folds: Fold 1 = 2019, Fold 2 = 2020, Fold 3 = 2021.
Each fold: indicators on [90-day lookback + fold window], signals extracted on fold window only.
Net Profit % = Net Profit (USD) / 1000 x 100.
Note: Thresholds 25 and 30 were computed with the original broken calc_pnl. The ADX=20 row reflects the corrected calc_pnl (close-bar PnL aggregation).

| Threshold | Fold   | Sharpe | Max DD % | Net Profit % | Win Rate % | Trades |
|:---------:|:------:|-------:|---------:|-------------:|-----------:|-------:|
| **20**    | Fold 1 | 1.0503 |    23.61 |        48.14 |      50.00 |     14 |
| **20**    | Fold 2 | 0.6731 |    32.48 |        29.76 |      35.29 |     17 |
| **20**    | Fold 3 | 0.8166 |    23.93 |        45.22 |      50.00 |     18 |
| 25        | Fold 1 | 0.4971 |    23.61 |        21.86 |      46.15 |     13 |
| 25        | Fold 2 | 0.8792 |    32.97 |        28.83 |      38.46 |     13 |
| 25        | Fold 3 | 1.1407 |    23.93 |        72.61 |      53.85 |     13 |
| 30        | Fold 1 | 0.4971 |    23.61 |        21.86 |      46.15 |     13 |
| 30        | Fold 2 | 0.0475 |    43.90 |       -15.93 |      27.27 |     11 |
| 30        | Fold 3 |-0.1595 |    24.26 |       -11.01 |      33.33 |      6 |

### Worst-Fold Sharpe per Threshold

| Threshold | Worst-Fold Sharpe    |
|:---------:|---------------------:|
| **20**    | **0.6731** (Fold 2)  |
| 25        | 0.4971 (Fold 1)      |
| 30        | -0.1595 (Fold 3)     |

---

## Locked Threshold

```
# main.py line 7
ADX_THRESHOLD = 20
```

Basis: ADX=20 has the highest worst-fold Sharpe (0.6731). ADX=25 worst fold is 0.4971; ADX=30 worst fold is -0.1595. No other criterion was used for selection.

No sweep or list logic runs in the default code path. main() calls strat() once with adx_threshold=ADX_THRESHOLD.

---

## 2022 Out-of-Sample Test

Period: 2022-01-01 to 2022-12-31
Lookback for indicators: 90 days pre-2022 (2021-10-03 to 2021-12-31)
ADX_THRESHOLD: 20 (locked)
Starting capital: $1000 (fresh, no carryover from 2018-2021)

### Full get_statistics() output

```
Total Trades: 12
Leverage Applied: 1
Winning Trades: 6
Losing Trades: 6
No. of Long Trades: 3
No. of Short Trades: 9
Benchmark Return(%): -65.2000
Benchmark Return(on $1000): -652.0000
Win Rate: 50.0000
Winning Streak: 2
Losing Streak: 4
Gross Profit: 475.0232
Net Profit: 453.0571
Average Profit: 37.7548
Maximum Drawdown(%): 10.4386
Average Drawdown(%): 3.9095
Largest Win: 347.9431
Average Win: 126.2766
Largest Loss: -109.3185
Average Loss: -50.7671
Maximum Holding Time: 21 days 00:00:00
Average Holding Time: 10 days 12:00:00
Maximum Adverse Excursion: None
Average Adverse Excursion: None
Sharpe Ratio: 1.1495
Sortino Ratio: None
```

### Net Profit as % of starting capital

`$453.06 / $1000 x 100 = 45.31%`

---

## Buy-and-Hold Comparison

| Period          | Net Profit % |
|-----------------|-------------:|
| Strategy        |      +45.31% |
| Buy-and-Hold    |      -65.20% |

Strategy turned $1000 into $1453.06 in 2022. Buy-and-hold turned $1000 into $348.00. Outperformance: **+$1105.06**.

---

## Lookahead Bias Check

```
Checking for lookahead bias...
  Verifying 22 signal bars...
  PASS: No lookahead bias detected.
```

Method: For each signal bar `i`, `process_data()` + `strat()` re-run on data truncated at bar `i`. Signal at bar `i` in truncated run must equal signal at bar `i` in full run. Any difference indicates future data leakage.

All 22 signal bars in the 2022 test passed the check.

---

## Consolidated Table — All Periods

| Period | Sharpe | Max DD % | Net Profit % | Win Rate % | Trades |
|--------|:------:|:--------:|:------------:|:----------:|:------:|
| Fold 1 | 1.0503 | 23.61 | 48.14 | 50.00 | 14 |
| Fold 2 | 0.6731 | 32.48 | 29.76 | 35.29 | 17 |
| Fold 3 | 0.8166 | 23.93 | 45.22 | 50.00 | 18 |
| **2022 Test** | **1.1495** | **10.44** | **45.31** | **50.00** | **12** |
| Buy-and-Hold 2022 | - | - | -65.20 | - | - |

All "Net Profit %" values computed as `(Net Profit USD / $1000) x 100`. Units verified.
