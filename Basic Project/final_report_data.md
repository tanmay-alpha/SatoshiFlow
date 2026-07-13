# BTC Strategy — Final Report Data

**Data file SHA-256:** `32814cd9f3b83dc79a0092c1f1c24bd988dad4c4b230dcd421401025ac660748`
**Dataset:** 1826 rows, 2018-01-01 to 2022-12-31
**Starting capital:** $1000

---

## Strategy Rationale (TBD)

---

## Threshold Sweep — Walk-Forward Validation

Folds: Fold 1 = 2019, Fold 2 = 2020, Fold 3 = 2021.
Each fold: indicators on [90-day lookback + fold window], signals extracted on fold window only.
Net Profit % = Net Profit (USD) / 1000 x 100.

| Threshold | Fold   | Sharpe | Max DD % | Net Profit % | Win Rate % | Trades |
|:---------:|:------:|-------:|---------:|-------------:|-----------:|-------:|
| **20**    | Fold 1 | 0.9294 |    23.61 |        48.14 |      50.00 |     14 |
| **20**    | Fold 2 | 0.9386 |    32.48 |        29.76 |      35.29 |     17 |
| **20**    | Fold 3 | 0.7982 |    23.93 |        45.22 |      50.00 |     18 |
| 25        | Fold 1 | 0.4971 |    23.61 |        21.86 |      46.15 |     13 |
| 25        | Fold 2 | 0.8792 |    32.97 |        28.83 |      38.46 |     13 |
| 25        | Fold 3 | 1.1407 |    23.93 |        72.61 |      53.85 |     13 |
| 30        | Fold 1 | 0.4971 |    23.61 |        21.86 |      46.15 |     13 |
| 30        | Fold 2 | 0.0475 |    43.90 |       -15.93 |      27.27 |     11 |
| 30        | Fold 3 |-0.1595 |    24.26 |       -11.01 |      33.33 |      6 |

### Worst-Fold Sharpe per Threshold

| Threshold | Worst-Fold Sharpe    |
|:---------:|---------------------:|
| **20**    | **0.7982** (Fold 3)  |
| 25        | 0.4971 (Fold 1)      |
| 30        | -0.1595 (Fold 3)     |

---

## Locked Threshold

`
# main.py line 7
ADX_THRESHOLD = 20
`

Basis: ADX=20 has the highest worst-fold Sharpe (0.7982). ADX=25 worst fold is 0.4971; ADX=30 worst fold is -0.1595. No other criterion was used for selection.

No sweep or list logic runs in the default code path. main() calls strat() once with adx_threshold=ADX_THRESHOLD.

---

## 2022 Out-of-Sample Test

Period: 2022-01-01 to 2022-12-31
Lookback for indicators: 90 days pre-2022
ADX_THRESHOLD: 20 (locked)

### Full get_statistics() output (unrounded, all keys)

`
Total Trades              : 12
Leverage Applied          : 1
Winning Trades            : 6
Losing Trades             : 6
No. of Long Trades        : 3
No. of Short Trades       : 9
Benchmark Return(%)       : -65.20000461
Benchmark Return(on ): -652.0000461
Win Rate                  : 50.0
Winning Streak            : 2
Losing Streak             : 4
Gross Profit              : 475.02319988
Net Profit                : 453.05710538
Average Profit            : 37.75475878
Maximum Drawdown(%)       : 10.43856831
Average Drawdown(%)       : 3.90951710
Largest Win               : 347.94313107
Average Win               : 126.27661357
Largest Loss              : -109.31853618
Average Loss              : -50.76709600
Maximum Holding Time      : 21 days 00:00:00
Average Holding Time      : 10 days 12:00:00
Maximum Adverse Excursion : None
Average Adverse Excursion : None
Sharpe Ratio              : 1.09633660
Sortino Ratio             : None
`

### Net Profit as % of starting capital

453.05710538 / 1000 x 100 = 45.31%

### Gross Profit definition (backtester.py line 230)

Gross Profit = net_profit + transaction_costs

Each trade.pnl() deducts transaction_fee x |qty|. net_profit is the sum of all pnl() values. transaction_costs is the raw sum of fees across all trades. Gross Profit is therefore the P&L with zero fees -- not the sum of winning trades.

---

## Buy-and-Hold Comparison (2022)

| Period          | Net Profit % |
|-----------------|-------------:|
| Strategy        |      +45.31% |
| Buy-and-Hold    |      -65.20% |

---

## Lookahead Bias Check

### main.py inline checker (2021 validation, 29 signal bars)

`
Checking for lookahead bias...
  Verifying 29 signal bars...
  PASS: No lookahead bias detected.
`

### lookahead_check.py standalone (full dataset)

`
Total rows in dataset: 1826
PASS: Signals for bars 0..299 are identical between 300-row and 500-row runs.
PASS: Signals for bars 0..499 are identical between 500-row and 700-row runs.
PASS: Signals for bars 0..699 are identical between 700-row and 1826-row runs.

LOOKAHEAD BIAS CHECK: PASS
No future data leakage detected. Signals at bar i are invariant to data appended after bar i.
`

Method: For each signal bar i, process_data() + strat() re-run on data truncated at bar i.
Signal at bar i in truncated run must equal signal at bar i in full run.
Any difference would indicate future data leakage.
