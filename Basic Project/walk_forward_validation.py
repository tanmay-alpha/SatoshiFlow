#!/usr/bin/env python3
"""
Walk-forward validation framework for BTC trading strategy.
"""

import pandas as pd
import numpy as np
from backtester import BackTester
from main import process_data, strat
import sys


def run_walk_forward_validation(data, adx_thresholds=[20, 25, 30]):
    """
    Run walk-forward validation with different ADX thresholds.

    Parameters:
    - data: DataFrame with datetime column
    - adx_thresholds: List of ADX thresholds to test

    Returns:
    - Dictionary of results for each threshold
    """
    results = {}

    # Add fold column based on year
    data['year'] = data['datetime'].dt.year
    data['fold'] = 0
    data.loc[data['year'] == 2018, 'fold'] = 1  # Train: 2018
    data.loc[data['year'] == 2019, 'fold'] = 2  # Val: 2019
    data.loc[data['year'].isin([2020, 2021]), 'fold'] = 3  # Train: 2019-2021, Val: 2022
    data.loc[data['year'] == 2022, 'fold'] = 4  # Test: 2022

    print("Fold configuration:")
    print(data['fold'].value_counts().sort_index())
    print()

    for threshold in adx_thresholds:
        print(f"=== Testing ADX Threshold: {threshold} ===")
        fold_results = {}

        # Fold 1: Train 2018, Val 2019
        train_1 = data[data['fold'] == 1].copy()
        val_1 = data[data['fold'] == 2].copy()

        # Process training data
        train_processed = process_data(train_1)

        # Backtest validation set
        val_processed = process_data(val_1)
        val_signals = strat(val_processed, adx_threshold=threshold)

        # Create temporary CSV for backtesting
        temp_path = f"temp_val_{threshold}_2019.csv"
        val_signals.to_csv(temp_path, index=False)

        # Run backtest
        bt = BackTester("BTC", signal_data_path=temp_path,
                        master_file_path=temp_path, compound_flag=1)
        bt.get_trades
        stats_1 = bt.get_statistics()

        fold_results['2019'] = stats_1

        print(f"  2019: Sharpe = {stats_1.get('Sharpe Ratio', 'N/A')}, "
              f"Win Rate = {stats_1.get('Win Rate', 'N/A')}%, "
              f"Trades = {stats_1.get('Total Trades', 'N/A')}")

        # Fold 2: Train 2019-2020, Val 2021
        train_2 = data[data['fold'] <= 2].copy()
        val_2 = data[data['fold'] == 3].copy()

        # Process training data
        train_processed = process_data(train_2)

        # Backtest validation set
        val_processed = process_data(val_2)
        val_signals = strat(val_signals, adx_threshold=threshold)

        # Create temporary CSV for backtesting
        temp_path = f"temp_val_{threshold}_2021.csv"
        val_signals.to_csv(temp_path, index=False)

        # Run backtest
        bt = BackTester("BTC", signal_data_path=temp_path,
                        master_file_path=temp_path, compound_flag=1)
        bt.get_trades
        stats_2 = bt.get_statistics()

        fold_results['2021'] = stats_2

        print(f"  2021: Sharpe = {stats_2.get('Sharpe Ratio', 'N/A')}, "
              f"Win Rate = {stats_2.get('Win Rate', 'N/A')}%, "
              f"Trades = {stats_2.get('Total Trades', 'N/A')}")

        # Store results for this threshold
        results[f"adx_{threshold}"] = fold_results

        # Clean up temp files
        import os
        if os.path.exists(f"temp_val_{threshold}_2019.csv"):
            os.remove(f"temp_val_{threshold}_2019.csv")
        if os.path.exists(f"temp_val_{threshold}_2021.csv"):
            os.remove(f"temp_val_{threshold}_2021.csv")

    return results


def find_optimal_threshold(results):
    """
    Find optimal ADX threshold based on worst-fold performance.
    """
    best_threshold = None
    best_worst_sharpe = -float('inf')

    print("\n" + "="*50)
    print("THRESHOLD OPTIMIZATION RESULTS")
    print("="*50)

    for threshold, fold_results in results.items():
        # Get Sharpe ratios for all folds
        sharpe_ratios = []
        for fold_key, stats in fold_results.items():
            sharpe = stats.get('Sharpe Ratio', 0)
            if sharpe != 'N/A':
                try:
                    sharpe_ratios.append(float(sharpe))
                except:
                    pass

        if sharpe_ratios:
            worst_sharpe = min(sharpe_ratios)
            avg_sharpe = np.mean(sharpe_ratios)

            print(f"\nThreshold {threshold}:")
            print(f"  Folds - Sharpe Ratios: {[f'{s:.3f}' for s in sharpe_ratios]}")
            print(f"  Worst fold Sharpe: {worst_sharpe:.3f}")
            print(f"  Average Sharpe: {avg_sharpe:.3f}")

            if worst_sharpe > best_worst_sharpe:
                best_worst_sharpe = worst_sharpe
                best_threshold = threshold

    print(f"\nOptimal threshold: {best_threshold} (worst-fold Sharpe: {best_worst_sharpe:.3f})")
    return best_threshold


def run_parameter_optimization():
    """
    Run full parameter optimization.
    """
    # Load data
    data = pd.read_csv("btc_18_22_1d.csv")
    data['datetime'] = pd.to_datetime(data['datetime'])

    # Test thresholds
    thresholds = [20, 25, 30]
    results = run_walk_forward_validation(data, thresholds)

    # Find optimal
    optimal = find_optimal_threshold(results)

    return optimal, results


if __name__ == "__main__":
    optimal_threshold, results = run_parameter_optimization()
    print(f"\nFinal recommendation: Use ADX threshold = {optimal_threshold}")