# SatoshiFlow BTC/USD strategy

SatoshiFlow is a reproducible submission for the organizer's BTC/USD
backtesting challenge. The official run imports and uses the original
`BackTester`; `backtester.py` remains unchanged at Git blob
`3b94f9749fb64e4fe271fae28d16628ea9fe2519`.

The supplied `btc_18_22_1d.csv` contains 1,826 daily rows from 2018-01-01
through 2022-12-31. The implementation remains generic and runs unchanged on
another valid evaluator-provided OHLCV CSV.

## Strategy

The fixed long/short strategy uses:

- a 30-day Donchian breakout calculated only from prior bars with `shift(1)`;
- 14-day Wilder ADX, threshold 20, and DI direction confirmation;
- a 200-day EMA regime filter;
- a 14-day Wilder ATR high/low trailing stop at 2.5 times ATR.

True Range, ATR, directional movement, DI, DX, ADX, EMA, and Donchian levels
are implemented from scratch in `main.py`. No TA-Lib, pandas-ta, vectorbt,
backtrader, or external strategy library is used.

## Execution compatibility

The original framework executes a signal at the signal row's close. To avoid
same-row execution bias, `strat()` forms a decision after completed candle
`t` and writes the corresponding organizer signal to candle `t+1`. The
framework therefore executes it at candle `t+1` close.

Signals follow the exact organizer convention:

- `0`: hold
- `1`: open long while flat, or close a short
- `-1`: open short while flat, or close a long
- `2`: reverse short to long
- `-2`: reverse long to short

A mechanical penultimate-row decision closes any remaining position on the
final row. It is separate from the economic strategy.

## Brokerage and metrics

The official run uses exactly $1,000 initial capital and the original
framework's 0.15% brokerage implementation. In that code,
`TradePair.pnl()` deducts 0.15% of absolute trade quantity once per completed
trade. This behavior is documented and is not changed.

The headline Sharpe ratio, maximum drawdown, win rate, total trades, net
profit, and benchmark return are returned by `BackTester.get_statistics()`.
The separate `research_backtest.py` is only a robustness audit: it evaluates
the same decisions at next open, charges 0.15% on entry and exit notionals,
and maintains a daily mark-to-market equity curve. Its results never replace
the organizer metrics.

## Data validation

The CLI requires `datetime`, `open`, `high`, `low`, `close`, and `volume`.
It sorts timestamps and rejects duplicate timestamps, missing/non-numeric
values, nonpositive OHLC values, invalid OHLC relationships, and negative
volume.

Dataset resolution order:

1. explicit `--data`
2. `BTC_2019_2023_1d.csv`
3. `btc_18_22_1d.csv`

## Installation

Python 3.10 or newer is required.

```powershell
cd "Basic Project"
python -m pip install -r requirements.txt
```

## Verified workflow

From `Basic Project`:

```powershell
python main.py --data btc_18_22_1d.csv
python research_backtest.py --data btc_18_22_1d.csv
python -m pytest -q
python generate_report.py
python verify_submission.py
```

`python main.py` also works without `--data` when a supported filename is
beside the script.

The official run prints these only after their assertions pass:

```text
LOOKAHEAD CHECK: PASS
SIGNAL SHIFT CHECK: PASS
ORGANIZER BACKTESTER CHECK: PASS
REPRODUCIBILITY CHECK: PASS
```

## Outputs

The official organizer run creates:

- `results/organizer/metrics.json`
- `results/organizer/trades.csv`
- `results/organizer/signals.csv`
- `results/organizer/equity_curve.png`
- `results/organizer/backtest_summary.txt`

The independent robustness run writes only under `results/research/`.
`generate_report.py` loads both JSON files, uses organizer values for all
headline metrics, and creates:

- `report.md`
- `SatoshiFlow_Report.pdf`
- `../SUBMIT_THESE/main.py`
- `../SUBMIT_THESE/SatoshiFlow_Report.pdf`

`SUBMIT_THESE/main.py` is self-contained apart from the organizer-supplied
`backtester.py` and the chosen CSV. It does not import repository helper
modules or use absolute paths.

## Tests

The 17-test suite checks manual ATR, recursive EMA, ADX sanity, shifted
Donchian levels, prefix and indicator invariance, one-row signal shifting,
no same-row execution, organizer signal validity, final liquidation, dataset
validation, full framework execution, exact reproducibility, submission-main
identity, and the original backtester blob.

See `FRAMEWORK_INTEGRITY.md` for the recovered framework comparison.
