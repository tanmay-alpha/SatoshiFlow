#!/usr/bin/env python3
"""
Consolidated runner: walk-forward on 2018-2021 + 2022 out-of-sample test.
ADX_THRESHOLD is locked -- no sweep logic.
Fresh $1000 base for 2022 (confirmed correct per Problem 2 analysis).
"""
import hashlib
import os
import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from backtester import BackTester
from main import process_data, strat, ADX_THRESHOLD

# =============================================================================
# LOCKED CONFIGURATION
# =============================================================================
CSV_PATH        = "btc_18_22_1d.csv"
LOOKBACK_DAYS   = 90
INITIAL_CAPITAL = 1000
THRESHOLD       = ADX_THRESHOLD   # single source of truth from main.py

FOLDS = [
    {"name": "Fold 1", "val_start": "2019-01-01", "val_end": "2019-12-31"},
    {"name": "Fold 2", "val_start": "2020-01-01", "val_end": "2020-12-31"},
    {"name": "Fold 3", "val_start": "2021-01-01", "val_end": "2021-12-31"},
]

TEST_START = "2022-01-01"
TEST_END   = "2022-12-31"
# =============================================================================


def csv_hash(path):
    """SHA-256 of file contents -- catches any silent data drift."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def load_data():
    data = pd.read_csv(CSV_PATH)
    data["datetime"] = pd.to_datetime(data["datetime"])
    return data


def run_fold(data, fold):
    """Walk-forward validation: indicators on full history, signals on fold only."""
    lookback = data[data["datetime"] < fold["val_start"]].tail(LOOKBACK_DAYS)
    val_window = data[
        (data["datetime"] >= fold["val_start"]) &
        (data["datetime"] <= fold["val_end"])
    ]
    combined = pd.concat([lookback, val_window], ignore_index=True).reset_index(drop=True)
    processed = process_data(combined)
    val_start_idx = len(lookback)
    val_result = processed.iloc[val_start_idx:].copy().reset_index(drop=True)
    val_result = strat(val_result)

    temp_path = f"temp_{fold['name'].replace(' ', '_')}.csv"
    val_result.to_csv(temp_path, index=False)
    bt = BackTester("BTC", signal_data_path=temp_path, master_file_path=temp_path, compound_flag=1)
    bt.get_trades(INITIAL_CAPITAL)
    stats = bt.get_statistics()
    if os.path.exists(temp_path):
        os.remove(temp_path)
    return stats, val_result, bt


def run_test(data):
    """2022 out-of-sample: fresh $1000, indicators from full 2018-2021 history."""
    lookback = data[data["datetime"] < TEST_START].tail(LOOKBACK_DAYS)
    test_window = data[
        (data["datetime"] >= TEST_START) &
        (data["datetime"] <= TEST_END)
    ]
    combined = pd.concat([lookback, test_window], ignore_index=True).reset_index(drop=True)
    processed = process_data(combined)
    test_start_idx = len(lookback)
    test_result = processed.iloc[test_start_idx:].copy().reset_index(drop=True)
    test_result = strat(test_result)

    temp_path = "temp_2022_test.csv"
    test_result.to_csv(temp_path, index=False)
    bt = BackTester("BTC", signal_data_path=temp_path, master_file_path=temp_path, compound_flag=1)
    bt.get_trades(INITIAL_CAPITAL)
    stats = bt.get_statistics()
    if os.path.exists(temp_path):
        os.remove(temp_path)
    return stats, test_result, bt


def buy_and_hold(data_df, initial_capital=INITIAL_CAPITAL):
    first_price = data_df["close"].iloc[0]
    last_price = data_df["close"].iloc[-1]
    shares = initial_capital / first_price
    final_value = shares * last_price
    return ((final_value - initial_capital) / initial_capital) * 100


def save_equity_curve(bt, title, filename):
    bt.calc_capital()
    fig, ax1 = plt.subplots(figsize=(14, 7))
    ax1.plot(bt.data.index, bt.data["close"], color="gray", alpha=0.7, label="BTC Close")
    ax1.set_xlabel("Date")
    ax1.set_ylabel("BTC Price (USD)", color="gray")
    ax1.tick_params(axis="y", labelcolor="gray")

    ax2 = ax1.twinx()
    ax2.plot(bt.data.index, bt.data["capital"], color="blue", label="Strategy Capital")
    ax2.set_ylabel("Capital (USD)", color="blue")
    ax2.tick_params(axis="y", labelcolor="blue")

    plt.title(title)
    fig.tight_layout()
    plt.savefig(filename, dpi=150)
    plt.close()
    print(f"  Saved: {filename}")


def pct(net_profit_usd):
    """Convert raw USD Net Profit to percentage return."""
    return net_profit_usd / INITIAL_CAPITAL * 100


def main():
    print("=" * 80)
    print(f"CONSOLIDATED RUN -- ADX_THRESHOLD={THRESHOLD} (locked)")
    print(f"Initial capital: ${INITIAL_CAPITAL}")
    print("=" * 80)

    # Data integrity guard
    fh = csv_hash(CSV_PATH)
    print(f"\nData file SHA-256: {fh}")
    print(f"(If this hash changes between runs, the CSV was modified -- results are not comparable.)")

    data = load_data()
    print(f"Loaded {len(data)} rows: {data['datetime'].iloc[0].date()} to {data['datetime'].iloc[-1].date()}")

    # ===== Walk-forward: 2018-2021 =====
    fold_stats = []
    print("\n--- WALK-FORWARD: 2018-2021 ---")
    for fold in FOLDS:
        stats, _, bt = run_fold(data, fold)
        if stats:
            fold_stats.append((fold["name"], stats))
            print(f"\n  {fold['name']} ({fold['val_start']} -> {fold['val_end']})")
            for k, v in stats.items():
                if isinstance(v, float):
                    print(f"    {k}: {v:.4f}")
                else:
                    print(f"    {k}: {v}")
        else:
            fold_stats.append((fold["name"], None))
            print(f"\n  {fold['name']}: No trades generated")

    # ===== 2022 out-of-sample test =====
    print("\n--- 2022 OUT-OF-SAMPLE TEST ---")
    stats_2022, test_result, bt_2022 = run_test(data)
    if stats_2022:
        print("\n  Full get_statistics() for 2022:")
        for k, v in stats_2022.items():
            if isinstance(v, float):
                print(f"    {k}: {v:.4f}")
            else:
                print(f"    {k}: {v}")
    else:
        print("  No trades generated for 2022")

    # ===== Buy-and-hold benchmark =====
    bah_pct = buy_and_hold(test_result)
    print(f"\n  Buy-and-Hold 2022 Return: {bah_pct:.2f}%")

    # ===== Equity curve =====
    if stats_2022:
        save_equity_curve(
            bt_2022,
            f"2022 Equity Curve -- Strategy vs Buy-and-Hold (ADX={THRESHOLD})",
            "equity_curve_2022.png",
        )

    # ===== Consolidated table =====
    print("\n" + "=" * 100)
    print("CONSOLIDATED TABLE -- ALL PERIODS")
    print("=" * 100)
    header = (
        f"{'Period':<20} | {'Sharpe':>10} | {'Max DD %':>10} | "
        f"{'Net Profit %':>12} | {'Win Rate %':>10} | {'Trades':>8}"
    )
    print(header)
    print("-" * 100)

    for name, stats in fold_stats:
        if stats:
            sharpe = stats["Sharpe Ratio"]
            max_dd = stats["Maximum Drawdown(%)"]
            np_val = pct(stats["Net Profit"])
            wr = stats["Win Rate"]
            trades = stats["Total Trades"]
            print(f"{name:<20} | {sharpe:>10.4f} | {max_dd:>10.2f} | {np_val:>12.2f} | {wr:>10.2f} | {trades:>8}")
        else:
            print(f"{name:<20} | {'N/A':>10} | {'N/A':>10} | {'N/A':>12} | {'N/A':>10} | {'0':>8}")

    if stats_2022:
        sharpe_22 = stats_2022.get("Sharpe Ratio", 0)
        max_dd_22 = stats_2022.get("Maximum Drawdown(%)", 0)
        np_22 = pct(stats_2022.get("Net Profit", 0))
        wr_22 = stats_2022.get("Win Rate", 0)
        trades_22 = stats_2022.get("Total Trades", 0)
        print(f"{'2022 Test':<20} | {sharpe_22:>10.4f} | {max_dd_22:>10.2f} | {np_22:>12.2f} | {wr_22:>10.2f} | {trades_22:>8}")
    else:
        print(f"{'2022 Test':<20} | {'N/A':>10} | {'N/A':>10} | {'N/A':>12} | {'N/A':>10} | {'0':>8}")

    print("-" * 100)
    print(f"{'Buy-and-Hold 2022':<20} | {'':>10} | {'':>10} | {bah_pct:>12.2f} | {'':>10} | {'':>8}")
    print("=" * 100)


if __name__ == "__main__":
    main()
