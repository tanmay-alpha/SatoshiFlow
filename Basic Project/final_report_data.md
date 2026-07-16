# BTC Strategy — Final Report Data

**Data file SHA-256:** `32814cd9f3b83dc79a0092c1f1c24bd988dad4c4b230dcd421401025ac660748`
**Dataset:** 1826 rows, 2018-01-01 to 2022-12-31
**Starting capital:** $1000
**Locked Threshold:** ADX_THRESHOLD = 20

---

## BLOCKING ISSUE

**`BTC_2019_2023_1d.csv` does not exist on this machine.** The assignment specifies data covering 2019–2023, but the only source data on disk is `btc_18_22_1d.csv` (2018–2022, 1826 rows). No file matching the assignment's required date range was found anywhere on this machine or in git history. This must be resolved by the user before the assignment can be completed with the correct dataset.

---

## Strategy Rationale (TBD)

---

## Threshold Sweep — Walk-Forward Validation

Folds: Fold 1 = 2019, Fold 2 = 2020, Fold 3 = 2021.
Each fold: indicators on [90-day lookback + fold window], signals extracted on fold window only.
Net Profit % = Net Profit (USD) / 1000 × 100.

| Threshold | Fold   | Sharpe | Max DD % | Net Profit % | Win Rate % | Trades |
|:---------:|:------:|-------:|---------:|-------------:|-----------:|-------:|
| **20**    | Fold 1 | 0.8757 |    23.61 |        42.03 |      55.00 |     20 |
| **20**    | Fold 2 | 0.9949 |    50.87 |        69.56 |      43.48 |     23 |
| **20**    | Fold 3 | 1.2456 |    23.72 |       105.71 |      54.17 |     24 |
| 25        | Fold 1 | 0.2265 |    23.61 |         1.28 |      47.06 |     17 |
| 25        | Fold 2 | 0.6974 |    55.38 |        32.61 |      42.11 |     19 |
| 25        | Fold 3 | 1.0005 |    23.72 |        70.20 |      50.00 |     20 |
| 30        | Fold 1 | 0.2265 |    23.61 |         1.28 |      47.06 |     17 |
| 30        | Fold 2 | 0.6113 |    46.88 |        24.58 |      41.18 |     17 |
| 30        | Fold 3 | 0.7096 |    27.09 |        20.31 |      58.33 |     12 |

### Worst-Fold Sharpe per Threshold

| Threshold | Worst-Fold Sharpe    |
|:---------:|---------------------:|
| **20**    | **0.8757** (Fold 1)  |
| 25        | 0.2265 (Fold 1)      |
| 30        | 0.2265 (Fold 1)     |

---

## Locked Threshold

```
# main.py line 7
ADX_THRESHOLD = 20
```

Basis: ADX=20 has the highest worst-fold Sharpe (0.8757). ADX=25 worst fold is 0.2265; ADX=30 worst fold is 0.2265. No other criterion was used for selection.

No sweep or list logic runs in the default code path. main() calls strat() once with adx_threshold=ADX_THRESHOLD.

---

## 2022 Out-of-Sample Test

Period: 2022-01-01 to 2022-12-31
Lookback for indicators: 90 days pre-2022 (2021-10-03 to 2021-12-31)
ADX_THRESHOLD: 20 (locked)
Starting capital: $1000 (fresh, no carryover from 2018-2021)

### Full get_statistics() output

```
Total Trades: 19
Leverage Applied: 1
Winning Trades: 11
Losing Trades: 8
No. of Long Trades: 8
No. of Short Trades: 11
Benchmark Return(%): -65.2000
Benchmark Return(on $1000): -652.0000
Win Rate: 57.8947
Winning Streak: 5
Losing Streak: 3
Gross Profit: 519.1579
Net Profit: 479.6954
Average Profit: 25.2471
Maximum Drawdown(%): 15.4188
Average Drawdown(%): 3.8097
Largest Win: 364.6433
Average Win: 107.5330
Largest Loss: -155.8648
Average Loss: -87.8959
Maximum Holding Time: 30 days 00:00:00
Average Holding Time: 10 days 22:44:12
Maximum Adverse Excursion: None
Average Adverse Excursion: None
Sharpe Ratio: 1.1014
Sortino Ratio: None
```

### Net Profit as % of starting capital

`$479.70 / $1000 × 100 = 47.97%`

---

## Buy-and-Hold Comparison

| Period          | Net Profit % |
|-----------------|-------------:|
| Strategy        |      +47.97% |
| Buy-and-Hold    |      -65.20% |

Strategy turned $1000 into $1479.70 in 2022. Buy-and-hold turned $1000 into $348.00. Outperformance: **+$1131.70**.

---

## Lookahead Bias Check

```
Checking for lookahead bias...
  Verifying 36 signal bars...
  PASS: No lookahead bias detected.
```

Method: For each signal bar `i`, `process_data()` + `strat()` re-run on data truncated at bar `i`. Signal at bar `i` in truncated run must equal signal at bar `i` in full run. Any difference indicates future data leakage.

All 36 signal bars in the 2022 test passed the check.

---

## Consolidated Table — All Periods

| Period | Sharpe | Max DD % | Net Profit % | Win Rate % | Trades |
|--------|:------:|:--------:|:------------:|:----------:|:------:|
| Fold 1 | 0.8757 | 23.61 | 42.03 | 55.00 | 20 |
| Fold 2 | 0.9949 | 50.87 | 69.56 | 43.48 | 23 |
| Fold 3 | 1.2456 | 23.72 | 105.71 | 54.17 | 24 |
| **2022 Test** | **1.1014** | **15.42** | **47.97** | **57.89** | **19** |
| Buy-and-Hold 2022 | - | - | -65.20 | - | - |

All "Net Profit %" values computed as `(Net Profit USD / $1000) × 100`. Units verified.

---

## Audit Log

| Check | Result |
|-------|--------|
| audit_run.py RUN_FINAL — two runs byte-identical | PASS |
| lookahead_check.py | PASS |
| run_2022.py | 2022 Sharpe 1.1014, Net Profit +47.97%, Max DD 15.42%, BAH -65.20% |
| walk_forward_eval.py | Net Profit % formula corrected (/1000×100) |
| main.py FIX 1 | Volume spike window excludes current bar (i-6:i-1) |
| main.py FIX 2 | bt.get_trades idiomatic call |
