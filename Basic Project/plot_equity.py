#!/usr/bin/env python3
"""
Equity curve plotting script for BTC trading strategy.
Plots portfolio equity alongside price data.
"""

import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from backtester import BackTester


def plot_equity_curve(bt, save_path=None):
    """
    Plot equity curve alongside price data.

    Parameters:
    - bt: BackTester instance
    - save_path: Optional path to save the plot
    """
    # Calculate capital if not already done
    bt.calc_capital()

    # Create figure with secondary y-axis
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))

    # Plot price data
    ax1.plot(bt.data.index, bt.data['close'], color='gray', alpha=0.7, label='BTC/USD')
    ax1.set_title('BTC/USD Price')
    ax1.set_ylabel('Price ($)')
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # Plot equity curve
    ax2.plot(bt.data.index, bt.data['capital'], color='blue', linewidth=2, label='Portfolio Equity')
    ax2.set_title('Portfolio Equity')
    ax2.set_ylabel('Capital ($)')
    ax2.set_xlabel('Date')
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    # Add trade regions to equity plot
    for trade in bt.trades:
        init_idx = bt.data.index.get_indexer([trade.init_timestamp], method='nearest')[0]
        final_idx = bt.data.index.get_indexer([trade.final_timestamp], method='nearest')[0]

        if 0 <= init_idx < len(bt.data) and 0 <= final_idx < len(bt.data):
            if trade.qty > 0:
                ax2.axvspan(bt.data.index[init_idx], bt.data.index[final_idx],
                           alpha=0.2, color='green')
            else:
                ax2.axvspan(bt.data.index[init_idx], bt.data.index[final_idx],
                           alpha=0.2, color='red')

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"Plot saved to {save_path}")
    else:
        plt.show()


def plot_performance_metrics(bt, save_path=None):
    """
    Plot performance metrics including drawdown and returns.
    """
    bt.calc_capital()

    # Calculate daily returns and drawdown
    daily_returns = bt.data['capital'].pct_change().dropna()
    cumulative_returns = (1 + daily_returns).cumprod() - 1
    running_max = bt.data['capital'].expanding().max()
    drawdown = (bt.data['capital'] - running_max) / running_max * 100

    # Create figure
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(12, 10))

    # Plot cumulative returns
    ax1.plot(bt.data.index, cumulative_returns * 100, color='blue', linewidth=2)
    ax1.set_title('Cumulative Returns')
    ax1.set_ylabel('Returns (%)')
    ax1.grid(True, alpha=0.3)
    ax1.axhline(y=0, color='black', linestyle='--', alpha=0.5)

    # Plot drawdown
    ax2.fill_between(bt.data.index, drawdown, 0, alpha=0.3, color='red')
    ax2.set_title('Drawdown')
    ax2.set_ylabel('Drawdown (%)')
    ax2.grid(True, alpha=0.3)

    # Plot daily returns
    ax3.bar(bt.data.index, daily_returns * 100, width=1, alpha=0.7, color='green')
    ax3.set_title('Daily Returns')
    ax3.set_ylabel('Return (%)')
    ax3.set_xlabel('Date')
    ax3.grid(True, alpha=0.3)

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"Performance plot saved to {save_path}")
    else:
        plt.show()


if __name__ == "__main__":
    # Example usage
    from main import process_data, strat

    # Load and process data
    data = pd.read_csv("btc_18_22_1d.csv")
    data['datetime'] = pd.to_datetime(data['datetime'])
    processed = process_data(data)

    # Run strategy
    strategy_data = strat(processed, adx_threshold=25)
    strategy_data.to_csv("final_data.csv", index=False)

    # Create backtester
    bt = BackTester("BTC", signal_data_path="final_data.csv",
                    master_file_path="final_data.csv", compound_flag=1)
    bt.get_trades

    # Plot equity curve
    plot_equity_curve(bt, save_path="equity_curve.png")

    # Plot performance metrics
    plot_performance_metrics(bt, save_path="performance_metrics.png")