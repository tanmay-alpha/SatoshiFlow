# SatoshiFlow BTC/USD strategy

SatoshiFlow is a reproducible submission for the organizer's BTC/USD
backtesting challenge. The strategy and indicators are implemented directly
with pandas and NumPy; TA-Lib, pandas-ta, and similar indicator libraries are
not used.

## Current data limitation

The challenge PDF names `BTC_2019_2023_1d.csv`, but that file is not present in
this repository. The only raw challenge-style dataset is
`btc_18_22_1d.csv`, containing 1,826 daily rows from 2018-01-01 through
2022-12-31.

Consequently, the committed metrics and report are explicitly **provisional**:
parameters were selected with 2019-2021 data and 2022 is the untouched
fallback out-of-sample period. They are not presented as official 2019-2023
results.

When the official file is supplied, place it in this directory and run the
same commands with `--data BTC_2019_2023_1d.csv`. The CLI prefers that filename
automatically when `--data` is omitted.

## Strategy

The fixed strategy uses:

- a 30-day Donchian breakout calculated from prior bars (`shift(1)`);
- 14-day Wilder ADX with threshold 20 and DI direction confirmation;
- a 200-day EMA regime filter;
- a 14-day Wilder ATR trailing stop at 2.5 times ATR;
- symmetric long and short rules.

All formulas are implemented from scratch in `main.py`. A decision uses the
completed candle at `t`, becomes pending, and executes only at the open of
`t+1`. The final open position, if any, is closed on the last bar.

## Accounting and metrics

Initial capital is exactly $1,000 and is fully deployed per trade. Brokerage is
0.15% of notional on entry and again on exit; a reversal closes the current
position and opens the new one. Daily equity is marked to market with
unrealized P&L.

- Daily return: `equity[t] / equity[t-1] - 1`
- Sharpe: `sqrt(365) * mean(daily returns) / sample std(daily returns)`
- Drawdown: `equity / running_max(equity) - 1`
- Win rate: winning completed trades / completed trades

The engine also reports final equity, net return, average trade, profit factor,
total brokerage, entries/exits/reversals, and buy-and-hold return.

## Installation

Python 3.10 or newer is required.

```powershell
cd "Basic Project"
python -m pip install -r requirements.txt
```

## Exact workflow

Run the small pre-test parameter validation:

```powershell
python validate_parameters.py --data btc_18_22_1d.csv
```

Run tests:

```powershell
python -m pytest -q
```

Run the verified fallback backtest:

```powershell
python main.py --data btc_18_22_1d.csv
```

Generate the PDF and submission folder from the latest metrics:

```powershell
python generate_report.py
```

The official-data workflow is identical except for the path:

```powershell
python main.py --data BTC_2019_2023_1d.csv
python generate_report.py
```

## Generated outputs

`python main.py` creates:

- `results/metrics.json`
- `results/trades.csv`
- `results/equity_curve.csv`
- `results/equity_curve.png`
- `results/drawdown.png`
- `results/backtest_summary.txt`

`python generate_report.py` creates:

- `report.md`
- `SatoshiFlow_Report.pdf`
- `../SUBMIT_THESE/main.py`
- `../SUBMIT_THESE/SatoshiFlow_Report.pdf`

The PDF reads every displayed performance number from `metrics.json`.

## Validation

`main.py` fails on missing columns, duplicate timestamps, missing values,
nonpositive OHLCV values, or invalid OHLC relationships. It prints the selected
filename, row count, date range, and SHA-256 hash.

Runtime assertions verify:

- prefix invariance across multiple cutoffs and all bars;
- indicator invariance when future rows are appended;
- execution no earlier than the next candle open;
- complete-run reproducibility, including trades, equity, and metrics.

The console prints `LOOKAHEAD CHECK: PASS` and
`REPRODUCIBILITY CHECK: PASS` only after all corresponding assertions succeed.

## Framework integrity

`backtester.py` is restored byte-for-byte at the Git blob level to the initial
organizer-provided version (`3b94f9749fb64e4fe271fae28d16628ea9fe2519`).
It remains available for organizer compatibility and is not modified.

The verified CLI uses the self-contained simulator in `main.py` because the
starter framework executes at current close, charges only one brokerage side,
does not force-close the final position, and does not produce the required
daily mark-to-market statistics. See `FRAMEWORK_INTEGRITY.md`.

## Submission files

Only these files are placed in `SUBMIT_THESE/`:

- `main.py`
- `SatoshiFlow_Report.pdf`

The organizer's `backtester.py` and dataset remain outside that folder, as
requested by the challenge instructions.
