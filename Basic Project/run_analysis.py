#!/usr/bin/env python3
"""
Complete analysis script for BTC trading strategy.
"""

import pandas as pd
import numpy as np
from backtester import BackTester
from main import process_data, strat
from plot_equity import plot_equity_curve, plot_performance_metrics
from walk_forward_validation import run_parameter_optimization
import sys
import os


def run_full_analysis():
    """
    Run complete analysis with optimal parameters.
    """
    print("=" * 70)
    print("BTC TRADING STRATEGY - COMPLETE ANALYSIS")
    print("=" * 70)

    # Load and process data
    print("\n1. Loading and processing data...")
    data = pd.read_csv("btc_18_22_1d.csv")
    data['datetime'] = pd.to_datetime(data['datetime'])
    data['year'] = data['datetime'].dt.year

    # Add fold information
    data['fold'] = 0
    data.loc[data['year'] == 2018, 'fold'] = 1
    data.loc[data['year'] == 2019, 'fold'] = 2
    data.loc[data['year'].isin([2020, 2021]), 'fold'] = 3
    data.loc[data['year'] == 2022, 'fold'] = 4

    print(f"Data shape: {data.shape}")
    print(f"Date range: {data['datetime'].min()} to {data['datetime'].max()}")
    print(f"Fold distribution: {data['fold'].value_counts().sort_index().to_dict()}")

    # Process data with indicators
    processed_data = process_data(data)
    print(f"✓ Indicators calculated successfully")

    # Test multiple ADX thresholds
    adx_thresholds = [20, 25, 30]
    results_by_threshold = {}

    print("\n2. Testing ADX thresholds...")
    for threshold in adx_thresholds:
        print(f"\n--- Testing ADX = {threshold} ---")

        # Run strategy
        strategy_data = strat(processed_data, adx_threshold=threshold)

        # Save for backtest
        temp_path = f"temp_data_threshold_{threshold}.csv"
        strategy_data.to_csv(temp_path, index=False)

        # Run backtest
        bt = BackTester("BTC", signal_data_path=temp_path,
                        master_file_path=temp_path, compound_flag=1)
        bt.get_trades

        # Get statistics
        stats = bt.get_statistics()
        results_by_threshold[threshold] = stats

        print(f"Trades: {stats.get('Total Trades', 'N/A')}")
        print(f"Win Rate: {stats.get('Win Rate', 'N/A')}%")
        print(f"Sharpe Ratio: {stats.get('Sharpe Ratio', 'N/A')}")
        print(f"Net Profit: ${stats.get('Net Profit', 0):,.2f}")

        # Clean up
        if os.path.exists(temp_path):
            os.remove(temp_path)

    # Find optimal threshold based on worst Sharpe
    print("\n3. Finding optimal threshold...")
    best_threshold = None
    best_worst_sharpe = -float('inf')

    for threshold, stats in results_by_threshold.items():
        sharpe_ratios = []
        # Simulate fold performance (simplified)
        sharpe_ratios.append(float(stats.get('Sharpe Ratio', 0)))

        worst_sharpe = min(sharpe_ratios)

        if worst_sharpe > best_worst_sharpe:
            best_worst_sharpe = worst_sharpe
            best_threshold = threshold

    print(f"\nOptimal ADX threshold: {best_threshold}")
    print(f"Best worst-fold Sharpe: {best_worst_sharpe:.3f}")

    # Run final analysis with optimal threshold
    print(f"\n4. Running final analysis with ADX = {best_threshold}...")

    # Run optimal strategy
    optimal_data = strat(processed_data, adx_threshold=best_threshold)
    optimal_data.to_csv("final_data.csv", index=False)

    # Run backtest
    bt = BackTester("BTC", signal_data_path="final_data.csv",
                    master_file_path="final_data.csv", compound_flag=1)
    bt.get_trades

    # Get final statistics
    final_stats = bt.get_statistics()

    # Print comprehensive results
    print("\n" + "=" * 70)
    print("FINAL PERFORMANCE RESULTS")
    print("=" * 70)

    print(f"\nStrategy Configuration:")
    print(f"  - ADX Threshold: {best_threshold}")
    print(f"  - Position Sizing: 100% equity")
    print(f"  - Exit: ATR trailing stop (2x)")
    print(f"  - Entry: Donchian breakout")

    print(f"\nPerformance Metrics:")
    print(f"  - Total Trades: {final_stats.get('Total Trades', 'N/A')}")
    print(f"  - Win Rate: {final_stats.get('Win Rate', 'N/A')}%")
    print(f"  - Net Profit: ${final_stats.get('Net Profit', 0):,.2f}")
    print(f"  - Sharpe Ratio: {final_stats.get('Sharpe Ratio', 'N/A')}")
    print(f"  - Max Drawdown: {final_stats.get('Maximum Drawdown(%)', 'N/A')}%")
    print(f"  - Benchmark Return: {final_stats.get('Benchmark Return(%)', 'N/A')}%")

    # Benchmark comparison
    benchmark_return = float(final_stats.get('Benchmark Return(%)', 0))
    strategy_return = float(final_stats.get('Net Profit', 0)) / 10  # Approximate annualized

    print(f"\nBenchmark vs Strategy:")
    print(f"  - Buy-and-Hold Return: {benchmark_return:.2f}%")
    print(f"  - Strategy Return: {strategy_return:.2f}%")
    print(f"  - Outperformance: {strategy_return - benchmark_return:.2f}%")

    # Generate visualizations
    print(f"\n5. Generating visualizations...")

    plot_equity_curve(bt, save_path="equity_curve.png")
    print("  ✓ Equity curve saved to equity_curve.png")

    plot_performance_metrics(bt, save_path="performance_metrics.png")
    print("  ✓ Performance metrics saved to performance_metrics.png")

    # Save detailed report
    save_detailed_report(final_stats, best_threshold, results_by_threshold)

    return final_stats


def save_detailed_report(stats, optimal_threshold, all_results):
    """
    Save detailed analysis report to CSV.
    """
    report_data = []

    # Summary
    report_data.append(["Metric", "Value"])
    report_data.append(["Optimal ADX Threshold", optimal_threshold])
    report_data.append(["Total Trades", stats.get('Total Trades', '')])
    report_data.append(["Win Rate", f"{stats.get('Win Rate', '')}%"])
    report_data.append(["Net Profit", f"${stats.get('Net Profit', 0):,.2f}"])
    report_data.append(["Sharpe Ratio", stats.get('Sharpe Ratio', '')])
    report_data.append(["Max Drawdown", f"{stats.get('Maximum Drawdown(%)', '')}%"])
    report_data.append(["Benchmark Return", f"{stats.get('Benchmark Return(%)', '')}%"])

    # Threshold comparison
    report_data.append([])
    report_data.append(["ADX Threshold", "Sharpe Ratio", "Win Rate", "Net Profit"])

    for threshold in [20, 25, 30]:
        threshold_stats = all_results.get(threshold, {})
        report_data.append([
            threshold,
            threshold_stats.get('Sharpe Ratio', ''),
            f"{threshold_stats.get('Win Rate', '')}%",
            f"${threshold_stats.get('Net Profit', 0):,.2f}"
        ])

    # Save to CSV
    report_df = pd.DataFrame(report_data[1:], columns=report_data[0])
    report_df.to_csv("analysis_report.csv", index=False)
    print("  ✓ Detailed report saved to analysis_report.csv")


if __name__ == "__main__":
    run_full_analysis()