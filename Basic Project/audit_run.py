#!/usr/bin/env python3
"""
Full pipeline audit: threshold sweep (folds 1-3, thresholds 20/25/30) + 2022 test.
Prints all numbers in deterministic format for diffing between runs.
"""
import hashlib, os, sys, json
import pandas as pd
import numpy as np
from backtester import BackTester
from main import process_data, strat

CSV_PATH = "btc_18_22_1d.csv"
LOOKBACK_DAYS = 90
INITIAL_CAPITAL = 1000

FOLDS = [
    {"name": "Fold 1", "val_start": "2019-01-01", "val_end": "2019-12-31"},
    {"name": "Fold 2", "val_start": "2020-01-01", "val_end": "2020-12-31"},
    {"name": "Fold 3", "val_start": "2021-01-01", "val_end": "2021-12-31"},
]
ADX_THRESHOLDS = [20, 25, 30]

def csv_hash(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()

def run_fold(data, fold, threshold):
    lookback = data[data["datetime"] < fold["val_start"]].tail(LOOKBACK_DAYS)
    val_window = data[
        (data["datetime"] >= fold["val_start"]) &
        (data["datetime"] <= fold["val_end"])
    ]
    combined = pd.concat([lookback, val_window], ignore_index=True).reset_index(drop=True)
    processed = process_data(combined)
    val_start_idx = len(lookback)
    val_result = processed.iloc[val_start_idx:].copy().reset_index(drop=True)
    val_result = strat(val_result, adx_threshold=threshold)

    temp_path = f"temp_audit_{fold['name'].replace(' ', '_')}_adx{threshold}.csv"
    val_result.to_csv(temp_path, index=False)
    bt = BackTester("BTC", signal_data_path=temp_path, master_file_path=temp_path, compound_flag=1)
    bt.get_trades(INITIAL_CAPITAL)
    stats = bt.get_statistics()
    if os.path.exists(temp_path):
        os.remove(temp_path)
    return stats

def run_2022_test(data, threshold):
    test_start = "2022-01-01"
    test_end = "2022-12-31"
    lookback = data[data["datetime"] < test_start].tail(LOOKBACK_DAYS)
    test_window = data[
        (data["datetime"] >= test_start) &
        (data["datetime"] <= test_end)
    ]
    combined = pd.concat([lookback, test_window], ignore_index=True).reset_index(drop=True)
    processed = process_data(combined)
    test_start_idx = len(lookback)
    test_result = processed.iloc[test_start_idx:].copy().reset_index(drop=True)
    test_result = strat(test_result, adx_threshold=threshold)

    temp_path = "temp_audit_2022.csv"
    test_result.to_csv(temp_path, index=False)
    bt = BackTester("BTC", signal_data_path=temp_path, master_file_path=temp_path, compound_flag=1)
    bt.get_trades(INITIAL_CAPITAL)
    stats = bt.get_statistics()
    if os.path.exists(temp_path):
        os.remove(temp_path)
    return stats

def main():
    run_label = sys.argv[1] if len(sys.argv) > 1 else "RUN"
    print(f"=== {run_label} ===")
    print(f"CSV SHA-256: {csv_hash(CSV_PATH)}")

    data = pd.read_csv(CSV_PATH)
    data['datetime'] = pd.to_datetime(data['datetime'])
    print(f"Rows: {len(data)}, Range: {data['datetime'].iloc[0].date()} to {data['datetime'].iloc[-1].date()}")

    # Threshold sweep
    all_results = {}
    for threshold in ADX_THRESHOLDS:
        for fold in FOLDS:
            stats = run_fold(data, fold, threshold)
            key = f"T{threshold}_{fold['name']}"
            if stats:
                all_results[key] = {
                    "Sharpe": round(stats["Sharpe Ratio"], 6),
                    "MaxDD": round(stats["Maximum Drawdown(%)"], 6),
                    "NetProfit": round(stats["Net Profit"], 6),
                    "NetProfitPct": round(stats["Net Profit"] / INITIAL_CAPITAL * 100, 6),
                    "WinRate": round(stats["Win Rate"], 6),
                    "Trades": stats["Total Trades"],
                }
            else:
                all_results[key] = {"Sharpe": 0, "MaxDD": 0, "NetProfit": 0, "NetProfitPct": 0, "WinRate": 0, "Trades": 0}

    # Worst-fold Sharpe per threshold
    for threshold in ADX_THRESHOLDS:
        sharpes = [all_results[f"T{threshold}_{f['name']}"]["Sharpe"] for f in FOLDS]
        worst = min(sharpes)
        all_results[f"T{threshold}_WorstFoldSharpe"] = worst

    # 2022 test
    stats_2022 = run_2022_test(data, 20)  # locked threshold = 20
    if stats_2022:
        all_results["2022_Test"] = {
            "Sharpe": round(stats_2022["Sharpe Ratio"], 6),
            "MaxDD": round(stats_2022["Maximum Drawdown(%)"], 6),
            "NetProfit": round(stats_2022["Net Profit"], 6),
            "NetProfitPct": round(stats_2022["Net Profit"] / INITIAL_CAPITAL * 100, 6),
            "WinRate": round(stats_2022["Win Rate"], 6),
            "Trades": stats_2022["Total Trades"],
        }
        all_results["2022_FullStats"] = {}
        for k, v in stats_2022.items():
            if isinstance(v, float):
                all_results["2022_FullStats"][k] = round(v, 8)
            else:
                all_results["2022_FullStats"][k] = str(v)
    else:
        all_results["2022_Test"] = "No trades"

    # Print everything as sorted JSON for deterministic diffing
    print(json.dumps(all_results, indent=2, sort_keys=True, default=str))

if __name__ == "__main__":
    main()
