#!/usr/bin/env python3
"""
Walk-forward evaluation with exact fold boundaries.
Fold 1: train=[2018-01-01,2018-12-31], validate=[2019-01-01,2019-12-31]
Fold 2: train=[2018-01-01,2019-12-31], validate=[2020-01-01,2020-12-31]
Fold 3: train=[2018-01-01,2020-12-31], validate=[2021-01-01,2021-12-31]
"""

import hashlib
import pandas as pd
import os
from backtester import BackTester
from main import process_data, strat

CSV_PATH = "btc_18_22_1d.csv"

def csv_hash(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(), b""):
            h.update(chunk)
    return h.hexdigest()

print(f"Data file SHA-256: {csv_hash(CSV_PATH)}")
print("(If this hash changes between runs, the CSV was modified.)")

# Load data
data = pd.read_csv(CSV_PATH)
data['datetime'] = pd.to_datetime(data['datetime'])

# Define exact fold boundaries
folds = [
    {"name": "Fold 1", "val_start": "2019-01-01", "val_end": "2019-12-31"},
    {"name": "Fold 2", "val_start": "2020-01-01", "val_end": "2020-12-31"},
    {"name": "Fold 3", "val_start": "2021-01-01", "val_end": "2021-12-31"},
]

# ADX thresholds to test
adx_thresholds = [20, 25, 30]

# Store results
results = []

for threshold in adx_thresholds:
    threshold_results = []

    for fold in folds:
        # Get validation window with lookback for indicators
        lookback_data = data[data['datetime'] < fold['val_start']].tail(90)
        val_window = data[
            (data['datetime'] >= fold['val_start']) &
            (data['datetime'] <= fold['val_end'])
        ]

        # Combine lookback + validation
        val_data = pd.concat([lookback_data, val_window], ignore_index=True)
        val_data = val_data.reset_index(drop=True)

        # Process with lookback data included for proper indicator calculation
        val_processed = process_data(val_data)

        # Extract only the validation portion (after lookback)
        val_only_start_idx = len(lookback_data)
        val_result = val_processed.iloc[val_only_start_idx:].copy()
        val_result = val_result.reset_index(drop=True)

        # Run strategy on validation portion only (ADX_THRESHOLD is now a global constant)
        val_result = strat(val_result, adx_threshold=threshold)

        # Save temporary CSV for backtester
        temp_path = f"temp_fold_{fold['name'].replace(' ', '_')}_adx{threshold}.csv"
        val_result.to_csv(temp_path, index=False)

        # Run backtest
        bt = BackTester("BTC", signal_data_path=temp_path, master_file_path=temp_path, compound_flag=1)
        bt.get_trades(1000)

        # Get statistics
        stats = bt.get_statistics()

        if stats:
            threshold_results.append({
                'Sharpe Ratio': stats.get('Sharpe Ratio', 0),
                'Max Drawdown %': stats.get('Maximum Drawdown(%)', 0),
                'Net Profit %': stats.get('Net Profit', 0) / 10,
                'Win Rate %': stats.get('Win Rate', 0),
                'Total Trade Count': stats.get('Total Trades', 0)
            })
        else:
            threshold_results.append({
                'Sharpe Ratio': 0,
                'Max Drawdown %': 0,
                'Net Profit %': 0,
                'Win Rate %': 0,
                'Total Trade Count': 0
            })

        # Clean up
        if os.path.exists(temp_path):
            os.remove(temp_path)

    # Calculate worst fold Sharpe for this threshold
    worst_fold_sharpe = min(r['Sharpe Ratio'] for r in threshold_results)

    # Add to results
    for i, fold in enumerate(folds):
        row = {
            'Threshold': threshold,
            'Fold': fold['name'],
            'Sharpe Ratio': threshold_results[i]['Sharpe Ratio'],
            'Max Drawdown %': threshold_results[i]['Max Drawdown %'],
            'Net Profit %': threshold_results[i]['Net Profit %'],
            'Win Rate %': threshold_results[i]['Win Rate %'],
            'Total Trade Count': threshold_results[i]['Total Trade Count'],
            'Worst Fold Sharpe': worst_fold_sharpe if i == 0 else ''
        }
        results.append(row)

# Create DataFrame
df = pd.DataFrame(results)

# Print table
print("\n" + "=" * 120)
print("WALK-FORWARD EVALUATION RESULTS")
print("=" * 120)
print(f"\nData Range: 2018-01-01 to 2021-12-31 (no 2022 data)")
print(f"Folds: 3 (train on prior years, validate on single year)")
print(f"Thresholds Tested: {adx_thresholds}")
print("\n")

# Print formatted table
header = f"{'Threshold':^12} | {'Fold':^8} | {'Sharpe Ratio':^12} | {'Max DD %':^10} | {'Net Profit %':^12} | {'Win Rate %':^11} | {'Trades':^8} | {'Worst Sharpe':^12}"
print(header)
print("-" * 120)

for _, row in df.iterrows():
    worst_sharpe = f"{row['Worst Fold Sharpe']:.4f}" if row['Worst Fold Sharpe'] != '' else ''
    print(f"{row['Threshold']:^12} | {row['Fold']:^8} | {row['Sharpe Ratio']:^12.4f} | {row['Max Drawdown %']:^10.2f} | {row['Net Profit %']:^12.2f} | {row['Win Rate %']:^11.2f} | {row['Total Trade Count']:^8} | {worst_sharpe:^12}")

print("=" * 120)
