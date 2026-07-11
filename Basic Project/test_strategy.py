#!/usr/bin/env python3
"""
Test script to verify the trading strategy works correctly.
"""

import pandas as pd
import sys
import os

# Add current directory to path
sys.path.append('.')

from main import process_data, strat


def test_indicators():
    """Test that all indicators calculate correctly."""
    print("Testing indicator calculations...")

    # Load sample data
    data = pd.read_csv("btc_18_22_1d.csv")
    data['datetime'] = pd.to_datetime(data['datetime'])

    # Process data
    processed = process_data(data)

    # Check required indicators
    required_indicators = ['ATR', 'ADX', 'DI+', 'DI-', 'ema_fast', 'ema_slow',
                          'donchian_high', 'donchian_low', 'volume_zscore',
                          'RSI', 'bb_upper', 'bb_lower']

    missing_indicators = []
    for indicator in required_indicators:
        if indicator not in processed.columns:
            missing_indicators.append(indicator)

    if missing_indicators:
        print(f"✗ Missing indicators: {missing_indicators}")
        return False

    # Check for NaN values (should be limited at start)
    nan_counts = processed[required_indicators].isnull().sum()
    if nan_counts.max() > len(processed) * 0.1:  # More than 10% NaN
        print("✗ Too many NaN values in indicators")
        return False

    print(f"✓ All {len(required_indicators)} indicators calculated successfully")
    print(f"  - Shape: {processed.shape}")
    print(f"  - Max NaN count: {nan_counts.max()}")
    return True


def test_strategy_logic():
    """Test strategy generates valid signals."""
    print("\nTesting strategy logic...")

    # Load sample data
    data = pd.read_csv("btc_18_22_1d.csv")
    data['datetime'] = pd.to_datetime(data['datetime'])

    # Process data
    processed = process_data(data)

    # Test different ADX thresholds
    for threshold in [20, 25, 30]:
        strategy_result = strat(processed, adx_threshold=threshold)

        # Check signals are valid
        valid_signals = [-2, -1, 0, 1, 2]
        invalid_signals = strategy_result[~strategy_result['signals'].isin(valid_signals)]['signals']

        if len(invalid_signals) > 0:
            print(f"✗ Invalid signals for ADX={threshold}: {invalid_signals.unique()}")
            return False

        # Check some trades were generated
        trade_signals = strategy_result[strategy_result['signals'] != 0]
        if len(trade_signals) == 0:
            print(f"⚠ No trades generated for ADX={threshold}")

        print(f"  ✓ ADX={threshold}: {len(trade_signals)} signals generated")

    print("✓ Strategy generates valid signals")
    return True


def test_no_lookahead():
    """Test no lookahead bias."""
    print("\nTesting no lookahead bias...")

    # Load sample data
    data = pd.read_csv("btc_18_22_1d.csv")
    data['datetime'] = pd.to_datetime(data['datetime'])

    # Process and run strategy
    processed = process_data(data)
    strategy_result = strat(processed, adx_threshold=25)

    # Check each signal independently
    lookahead_errors = 0
    for i in range(len(strategy_result)):
        if strategy_result.loc[i, 'signals'] != 0:
            # Use only data up to point i
            temp_data = data.iloc[:i+1].copy()
            temp_processed = process_data(temp_data)
            temp_strategy = strat(temp_processed, adx_threshold=25)

            if temp_strategy.loc[i, 'signals'] != strategy_result.loc[i, 'signals']:
                lookahead_errors += 1

    if lookahead_errors > 0:
        print(f"✗ Found {lookahead_errors} lookahead bias errors")
        return False

    print("✓ No lookahead bias detected")
    return True


def main():
    """Run all tests."""
    print("=" * 50)
    print("BTC TRADING STRATEGY - TEST SUITE")
    print("=" * 50)

    # Check if data file exists
    if not os.path.exists("btc_18_22_1d.csv"):
        print("✗ Data file not found: btc_18_22_1d.csv")
        return False

    # Run tests
    tests = [
        test_indicators,
        test_strategy_logic,
        test_no_lookahead
    ]

    passed = 0
    total = len(tests)

    for test in tests:
        if test():
            passed += 1
        print()

    print("=" * 50)
    print(f"TEST RESULTS: {passed}/{total} passed")

    if passed == total:
        print("✓ All tests passed!")
        return True
    else:
        print("✗ Some tests failed")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)