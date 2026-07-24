# SatoshiFlow

## Overview

SatoshiFlow is a BTC/USD quantitative trading and backtesting project built for the Summer Quant challenge. It implements a deterministic long/short trend strategy using the challenge's original, unmodified `BackTester` framework.

## Strategy

The fixed-parameter strategy combines four technical indicators:

- **30-day Donchian breakout** -- a long triggers when close exceeds the prior-bar Donchian high; a short triggers when close falls below the prior-bar Donchian low. Levels are calculated using `shift(1)` so candle `t` cannot be included in its own breakout level.
- **ADX 14 with threshold 20** -- Wilder's Average Directional Index filters for trending regimes. Only ADX >= 20 allows entries.
- **DI direction confirmation** -- `DI+ > DI-` confirms longs; `DI- > DI+` confirms shorts.
- **EMA 200 regime filter** -- longs require price above EMA200; shorts require price below EMA200.

**Exits and reversals:**

- **ATR 14 trailing stop** -- set at entry at 2.5x ATR from the execution close; ratcheted to the most favorable high (long) or low (short) observed since entry.
- **Reversal** -- an opposite confirmed breakout closes the current position and opens the new one (signal +/-2).
- **Final liquidation** -- any position still open at the penultimate bar is mechanically closed on the final bar.

## Bias prevention

The strategy is designed to eliminate all lookahead and same-row execution bias:

1. Donchian levels use prior bars only (`shift(1)`) -- candle `t` cannot influence its own level.
2. A decision is formed after candle `t` closes.
3. The executable signal is written to candle `t+1`.
4. The organizer `BackTester` executes the signal at candle `t+1` close.

This means the strategy never sees or acts on the same bar where it decides. Prefix invariance tests at five dataset cutoffs confirm that indicators and decisions on any prefix match the corresponding slice of the full run.

## Organizer compatibility

- The original `backtester.py` is **unchanged** (Git blob `3b94f9749fb64e4fe271fae28d16628ea9fe2519`).
- `main.py` imports `BackTester` directly: `from backtester import BackTester`.
- Valid signals are exactly `0, +/-1, and +/-2` per the organizer state machine.
- Initial capital: **$1,000**.
- Brokerage: **0.15%** -- deducted once per completed trade inside `TradePair.pnl()`.

## Installation

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r "Basic Project/requirements.txt"
```

Linux / macOS:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r "Basic Project/requirements.txt"
```

## Running

```powershell
cd "Basic Project"
python main.py --data btc_18_22_1d.csv
```

## Testing

```powershell
python -m pytest -q
python verify_submission.py
```

## Results

Official organizer-framework metrics (loaded programmatically from `results/organizer/metrics.json`):

| Metric | Value |
|---|---:|
| Initial / final capital | $1,000.00 / $5,463.61 |
| Net return | 446.36% |
| Sharpe ratio | 1.012 |
| Maximum drawdown | 21.37% |
| Win rate | 55.17% |
| Completed trades | 29 |
| Buy-and-hold benchmark | 23.64% |

## Research robustness test

`research_backtest.py` is a stricter **independent** simulator that evaluates the same fixed decisions using:

- Next-open execution (vs. next-close in the organizer).
- Two-sided brokerage (0.15% on entry notional + 0.15% on exit notional).
- Daily mark-to-market equity curve.

These metrics are clearly secondary diagnostics and are intentionally separated from the organizer headline table in the PDF.

## Repository structure

```
SatoshiFlow/
|-- README.md                  <- this file
|-- FINAL_CHECKLIST.md
|-- .gitignore
|-- .gitattributes
|-- Basic Project/
|   |-- main.py
|   |-- backtester.py
|   |-- research_backtest.py
|   |-- generate_report.py
|   |-- verify_submission.py
|   |-- btc_18_22_1d.csv
|   |-- requirements.txt
|   |-- tests/test_main.py
|   |-- results/
|       |-- organizer/          <- official metrics
|       |-- research/           <- independent robustness metrics
|       |-- stress/             <- scaling and stress tests
|-- SUBMIT_THESE/
    |-- main.py
    |-- SatoshiFlow_Report.pdf
```

## Submission

Only these two files are submitted:

- `SUBMIT_THESE/main.py`
- `SUBMIT_THESE/SatoshiFlow_Report.pdf`

## Disclaimer

Historical backtesting does not guarantee future trading performance.
