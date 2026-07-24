#!/usr/bin/env python3
"""Synthetic engine stress test for SatoshiFlow.

Generates a deterministic synthetic OHLCV / signal stream sufficient to
exercise ONE MILLION completed trade records through a streaming backtest
engine.  This is a SCALABILITY test only -- the results are NOT real BTC
strategy performance.

A fixed random seed ensures reproducibility.  The engine processes the
stream with minimal Python-object allocation and reports timing, memory,
and reproducibility.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import time
import tracemalloc
from pathlib import Path

import numpy as np
import pandas as pd

try:
    import psutil

    _HAS_PSUTIL = True
except ImportError:
    _HAS_PSUTIL = False

DEFAULT_INITIAL_CAPITAL = 1_000_000.0
BROKERAGE_RATE = 0.0015
SYNTHETIC_SEED = 20260724


def _make_synthetic_stream(num_trades: int, seed: int = SYNTHETIC_SEED):
    """Return (ohlcv_df, signals_series) producing exactly ``num_trades``.

    Signal pattern (organizer convention):
        1, -1, -1, 1, 1, -1, -1, 1, ...  (repeat)
    This closes every trade on the next bar.  Every 100th trade is a
    reversal (signal ±2) to exercise that code path.

    Prices follow a sine-wave trend so both long and short trades can win.
    """
    rng = np.random.default_rng(seed)
    # 2 rows per trade (entry + exit), +1 for a possible trailing exit
    num_rows = 2 * num_trades + 1

    # Mean-reverting price around 10,000 with bounded noise.
    rho = 0.9995  # AR(1) persistence
    close = np.full(num_rows, 10_000.0, dtype=np.float64)
    for i in range(1, num_rows):
        close[i] = rho * close[i - 1] + (1 - rho) * 10_000.0 + rng.normal(0, 3.0)
    close = np.maximum(close, 1.0)

    high = close + rng.uniform(5, 30, size=num_rows)
    low = close - rng.uniform(5, 30, size=num_rows)
    open_ = np.clip(close + rng.normal(0, 5, size=num_rows), low, high)
    high = np.maximum(high, open_)
    low = np.minimum(low, open_)
    volume = rng.uniform(100, 10_000, size=num_rows)

    # Wilder-smoothed ATR (period 14)
    tr = np.maximum(
        high - low,
        np.maximum(
            np.abs(high - np.concatenate([[close[0]], close[:-1]])),
            np.abs(low - np.concatenate([[close[0]], close[:-1]])),
        ),
    )
    atr = np.full(num_rows, np.nan, dtype=np.float64)
    if num_rows >= 14:
        atr[13] = tr[:14].mean()
        for i in range(14, num_rows):
            atr[i] = atr[i - 1] + (tr[i] - atr[i - 1]) / 14.0

    datetimes = pd.date_range("2020-01-01", periods=num_rows, freq="min")
    ohlcv = pd.DataFrame(
        {
            "datetime": datetimes,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
            "ATR": atr,
        }
    )

    # Build alternating signal pattern: 1, -1 (long entry, long exit),
    # then -1, 1 (short entry, short exit), repeating.
    # Every 200th trade is a reversal.
    signals = np.zeros(num_rows, dtype=np.int64)
    pos = 0
    trade_count = 0
    flip = True  # True → long trade, False → short trade
    for i in range(num_rows):
        if pos == 0:
            if trade_count > 0 and trade_count % 200 == 0:
                # reversal: use signal ±2
                signals[i] = 2 if flip else -2
                pos = 1 if flip else -1
            else:
                signals[i] = 1 if flip else -1
                pos = 1 if flip else -1
            flip = not flip
        else:
            signals[i] = -pos  # close current position
            pos = 0
            trade_count += 1

    # Close any dangling open position on the last row
    if pos != 0:
        signals[num_rows - 1] = -pos
        trade_count += 1

    signal_df = pd.DataFrame(
        {
            "datetime": datetimes,
            "signals": signals,
            "TP": 0,
            "SL": 0,
        }
    )
    return ohlcv, signal_df, trade_count


def run_stress_backtest(
    signals: np.ndarray,
    closes: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    atrs: np.ndarray,
    initial_capital: float,
    num_trades: int,
) -> dict:
    """Streaming backtest loop using raw numpy arrays.  Minimal allocations."""
    n = len(signals)
    cash = float(initial_capital)
    quantity = 0.0
    position = 0
    trailing_stop = math.nan
    highest_since = -math.inf
    lowest_since = math.inf

    entry_price = 0.0
    trade_count = 0
    wins = 0
    losses = 0
    total_fees = 0.0
    max_equity = cash
    max_drawdown = 0.0
    gross_pnl_sum = 0.0

    # Track only the last trade's entry fee for PnL accounting
    entry_fee = 0.0

    for i in range(1, n + 1):
        sig = int(signals[i - 1]) if i <= n else 0
        c = float(closes[i - 1])

        if sig == 0:
            pass
        elif abs(sig) == 1:
            if position == 0:
                notional = cash / (1.0 + BROKERAGE_RATE)
                fee = notional * BROKERAGE_RATE
                quantity = math.copysign(notional / c, sig)
                cash -= math.copysign(notional + fee, sig)
                position = int(math.copysign(1, sig))
                entry_price = c
                entry_fee = fee
                trailing_stop = (
                    c - 2.5 * atrs[i - 1] if position == 1 else c + 2.5 * atrs[i - 1]
                )
                highest_since = c
                lowest_since = c
                total_fees += fee
            else:
                # close position
                exit_price = c
                exit_notional = abs(quantity) * exit_price
                exit_fee = exit_notional * BROKERAGE_RATE
                cash += math.copysign(exit_notional - exit_fee, -quantity)
                gross = position * abs(quantity) * (exit_price - entry_price) / entry_price
                net = gross - entry_fee - exit_fee
                gross_pnl_sum += gross
                total_fees += exit_fee
                if net > 0:
                    wins += 1
                else:
                    losses += 1
                trade_count += 1
                position = 0
                quantity = 0.0
                trailing_stop = math.nan
        elif abs(sig) == 2:
            # reverse: close current, open new
            if position != 0:
                exit_notional = abs(quantity) * c
                exit_fee = exit_notional * BROKERAGE_RATE
                cash += math.copysign(exit_notional - exit_fee, -quantity)
                gross = position * abs(quantity) * (c - entry_price) / entry_price
                gross_pnl_sum += gross
                total_fees += exit_fee
                if gross > 0:
                    wins += 1
                else:
                    losses += 1
                trade_count += 1
            new_dir = int(math.copysign(1, sig))
            notional = cash / (1.0 + BROKERAGE_RATE)
            fee = notional * BROKERAGE_RATE
            quantity = math.copysign(notional / c, new_dir)
            cash -= math.copysign(notional + fee, new_dir)
            position = new_dir
            entry_price = c
            entry_fee = fee
            trailing_stop = (
                c - 2.5 * atrs[i - 1] if position == 1 else c + 2.5 * atrs[i - 1]
            )
            highest_since = c
            lowest_since = c
            total_fees += fee

        equity = cash + quantity * c
        if equity > max_equity:
            max_equity = equity
        if max_equity > 0:
            dd = (max_equity - equity) / max_equity
            if dd > max_drawdown:
                max_drawdown = dd

    # Close any open position at last close
    if position != 0:
        c = float(closes[-1])
        exit_notional = abs(quantity) * c
        exit_fee = exit_notional * BROKERAGE_RATE
        cash += math.copysign(exit_notional - exit_fee, -quantity)
        gross = position * abs(quantity) * (c - entry_price) / entry_price
        gross_pnl_sum += gross
        total_fees += exit_fee
        if gross > 0:
            wins += 1
        else:
            losses += 1
        trade_count += 1

    final_equity = cash
    net_profit = final_equity - initial_capital
    win_rate = 100.0 * wins / trade_count if trade_count > 0 else 0.0
    profit_factor = (
        float(wins / losses)
        if losses > 0 and wins > 0
        else (None if wins == 0 else 0.0)
    )

    return {
        "requested_trades": num_trades,
        "completed_trades": trade_count,
        "final_equity": final_equity,
        "net_pnl": net_profit,
        "win_rate": win_rate,
        "total_fees": total_fees,
        "maximum_drawdown": max_drawdown * 100.0,
        "profit_factor": profit_factor,
        "gross_profit": gross_pnl_sum,
        "wins": wins,
        "losses": losses,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--trades",
        type=int,
        default=1_000_000,
        help="target completed trade count (default: 1000000)",
    )
    parser.add_argument(
        "--initial-capital",
        type=float,
        default=DEFAULT_INITIAL_CAPITAL,
        help=f"starting equity (default: {DEFAULT_INITIAL_CAPITAL:,.0f})",
    )
    parser.add_argument(
        "--output",
        default="Basic Project/results/stress/million_trade_stress.json",
        help="output JSON path",
    )
    args = parser.parse_args(argv)

    print(f"Generating synthetic stream for {args.trades:,} target trades...")
    t0 = time.perf_counter()
    ohlcv_df, signal_df, actual_trades = _make_synthetic_stream(args.trades)
    sig_arr = signal_df["signals"].to_numpy(dtype=np.int64)
    close_arr = ohlcv_df["close"].to_numpy(dtype=np.float64)
    high_arr = ohlcv_df["high"].to_numpy(dtype=np.float64)
    low_arr = ohlcv_df["low"].to_numpy(dtype=np.float64)
    atr_arr = ohlcv_df["ATR"].to_numpy(dtype=np.float64)
    gen_time = time.perf_counter() - t0
    print(
        f"  Generated {len(ohlcv_df):,} rows, "
        f"{actual_trades:,} trades in {gen_time:.2f}s"
    )

    print("Running stress backtest (run 1)...")
    tracemalloc.start()
    t1 = time.perf_counter()
    m1 = run_stress_backtest(
        sig_arr, close_arr, high_arr, low_arr, atr_arr,
        float(args.initial_capital), args.trades,
    )
    wall_time_1 = time.perf_counter() - t1
    current_mem, peak_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    if _HAS_PSUTIL:
        process = psutil.Process(os.getpid())
        rss_mb = process.memory_info().rss / 1024 / 1024
    else:
        rss_mb = peak_mem / 1024 / 1024

    print("Running stress backtest (run 2 - reproducibility)...")
    t2 = time.perf_counter()
    m2 = run_stress_backtest(
        sig_arr, close_arr, high_arr, low_arr, atr_arr,
        float(args.initial_capital), args.trades,
    )
    wall_time_2 = time.perf_counter() - t2

    reproducible = (
        m1["completed_trades"] == m2["completed_trades"]
        and m1["final_equity"] == m2["final_equity"]
        and m1["win_rate"] == m2["win_rate"]
        and m1["total_fees"] == m2["total_fees"]
        and m1["maximum_drawdown"] == m2["maximum_drawdown"]
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "test": "one_million_trade_engine_stress",
        "synthetic": True,
        "synthetic_note": (
            "SCALABILITY test using deterministic synthetic data. "
            "NOT real BTC strategy performance."
        ),
        "seed": SYNTHETIC_SEED,
        "requested_trades": args.trades,
        "completed_trades": m1["completed_trades"],
        "rows_processed": len(ohlcv_df),
        "initial_capital": float(args.initial_capital),
        "final_equity": m1["final_equity"],
        "net_pnl": m1["net_pnl"],
        "win_rate": m1["win_rate"],
        "total_fees": m1["total_fees"],
        "maximum_drawdown": m1["maximum_drawdown"],
        "profit_factor": m1["profit_factor"],
        "wins": m1["wins"],
        "losses": m1["losses"],
        "gross_profit": m1["gross_profit"],
        "runtime_seconds_run1": wall_time_1,
        "runtime_seconds_run2": wall_time_2,
        "peak_memory_kb": peak_mem / 1024,
        "rss_mb": rss_mb,
        "reproducibility": {
            "identical": reproducible,
            "run2_trades": m2["completed_trades"],
            "run2_equity": m2["final_equity"],
            "run2_win_rate": m2["win_rate"],
            "run2_fees": m2["total_fees"],
            "run2_drawdown": m2["maximum_drawdown"],
        },
    }
    output_path.write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )

    print(f"\n--- STRESS TEST RESULTS ---")
    print(f"  Requested trades:     {args.trades:,}")
    print(f"  Completed trades:     {m1['completed_trades']:,}")
    print(f"  Rows processed:       {len(ohlcv_df):,}")
    print(f"  Runtime (run 1):      {wall_time_1:.2f}s")
    print(f"  Runtime (run 2):      {wall_time_2:.2f}s")
    print(f"  Peak memory:          {peak_mem / 1024 / 1024:.1f} MB")
    print(f"  RSS:                  {rss_mb:.1f} MB")
    print(f"  Final equity:         ${m1['final_equity']:,.2f}")
    print(f"  Net PnL:              ${m1['net_pnl']:,.2f}")
    print(f"  Win rate:             {m1['win_rate']:.2f}%")
    print(f"  Total fees:           ${m1['total_fees']:,.2f}")
    print(f"  Max drawdown:         {m1['maximum_drawdown']:.2f}%")
    print(f"  Wins / Losses:        {m1['wins']:,} / {m1['losses']:,}")
    print(f"  Reproducible:         {reproducible}")
    print(f"  Output:               {output_path}")

    if not reproducible:
        print("WARNING: Reproducibility check FAILED", file=sys.stderr)
        return 1

    print("STRESS TEST: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
