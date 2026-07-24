"""Integrity tests for the self-contained submission module."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from main import (  # noqa: E402
    BROKERAGE_RATE,
    StrategyConfig,
    calculate_atr,
    calculate_ema,
    load_dataset,
    process_data,
    run_backtest,
    strat,
)


def ohlcv(rows: int = 260) -> pd.DataFrame:
    index = np.arange(rows, dtype=float)
    close = 100.0 + 0.2 * index + 2.0 * np.sin(index / 9.0)
    return pd.DataFrame(
        {
            "datetime": pd.date_range("2020-01-01", periods=rows, freq="D"),
            "open": close - 0.2,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": 1_000.0 + index,
        }
    )


def test_atr_matches_manual_wilder_example() -> None:
    data = pd.DataFrame(
        {
            "high": [11.0, 12.0, 13.0, 14.0],
            "low": [9.0, 9.0, 11.0, 10.0],
            "close": [10.0, 11.0, 12.0, 13.0],
        }
    )
    actual = calculate_atr(data, period=3)
    assert np.isnan(actual.iloc[0])
    assert np.isnan(actual.iloc[1])
    assert actual.iloc[2] == pytest.approx(7.0 / 3.0)
    assert actual.iloc[3] == pytest.approx(26.0 / 9.0)


def test_ema_recursive_behavior() -> None:
    actual = calculate_ema(pd.Series([10.0, 12.0, 14.0]), period=3)
    assert actual.tolist() == pytest.approx([10.0, 11.0, 12.5])


def test_donchian_is_shifted() -> None:
    data = ohlcv(8)
    config = StrategyConfig(
        donchian_period=3, adx_period=2, ema_period=3, atr_period=2
    )
    result = process_data(data, config)
    assert np.isnan(result.loc[2, "donchian_high"])
    assert result.loc[3, "donchian_high"] == pytest.approx(
        data.loc[0:2, "high"].max()
    )
    changed = data.copy()
    changed.loc[3, "high"] = 10_000.0
    changed_result = process_data(changed, config)
    assert changed_result.loc[3, "donchian_high"] == result.loc[3, "donchian_high"]


def test_prefix_and_indicator_invariance() -> None:
    data = ohlcv(300)
    full_indicators = process_data(data)
    full_signals = strat(full_indicators)
    prefix_indicators = process_data(data.iloc[:250].copy())
    prefix_signals = strat(prefix_indicators)
    pd.testing.assert_series_equal(
        prefix_signals["signals"],
        full_signals.loc[:249, "signals"],
        check_names=False,
    )
    for column in ("atr", "adx", "donchian_high", "donchian_low"):
        pd.testing.assert_series_equal(
            prefix_indicators[column],
            full_indicators.loc[:249, column],
            check_names=False,
        )


def test_signal_state_transitions() -> None:
    data = pd.DataFrame(
        {
            "datetime": pd.date_range("2020-01-01", periods=3, freq="D"),
            "open": [9.0, 10.0, 10.0],
            "high": [10.0, 11.0, 11.0],
            "low": [8.0, 9.0, 5.0],
            "close": [9.0, 11.0, 6.0],
            "volume": [1.0, 1.0, 1.0],
            "atr": [1.0, 1.0, 1.0],
            "adx": [30.0, 30.0, 30.0],
            "di_plus": [20.0, 20.0, 20.0],
            "di_minus": [10.0, 10.0, 10.0],
            "ema_regime": [8.0, 8.0, 8.0],
            "donchian_high": [10.0, 10.0, 12.0],
            "donchian_low": [7.0, 7.0, 4.0],
        }
    )
    config = StrategyConfig(
        donchian_period=1,
        adx_period=1,
        ema_period=1,
        atr_period=1,
        atr_stop_multiplier=2.5,
    )
    result = strat(data, config)
    assert result["signals"].tolist() == [0, 1, -1]
    assert np.isnan(result.loc[0, "decision_target"])
    assert result.loc[1, "decision_target"] == 1
    assert result.loc[2, "decision_target"] == 0


def execution_fixture() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "datetime": pd.date_range("2020-01-01", periods=3, freq="D"),
            "open": [100.0, 110.0, 120.0],
            "high": [101.0, 111.0, 121.0],
            "low": [99.0, 109.0, 119.0],
            "close": [100.5, 110.5, 120.5],
            "volume": [1.0, 1.0, 1.0],
            "decision_target": [1.0, np.nan, np.nan],
            "decision_reason": ["TEST", "HOLD", "HOLD"],
        }
    )


def test_next_open_execution_fees_and_force_close() -> None:
    metrics, trades, _ = run_backtest(execution_fixture())
    trade = trades.iloc[0]
    assert trade["entry_time"] == pd.Timestamp("2020-01-02")
    assert trade["entry_price"] == 110.0
    assert trade["exit_price"] == 120.5
    assert bool(trade["forced_exit"])
    expected_notional = 1_000.0 / (1.0 + BROKERAGE_RATE)
    expected_quantity = expected_notional / 110.0
    expected_entry_fee = expected_notional * BROKERAGE_RATE
    expected_exit_fee = expected_quantity * 120.5 * BROKERAGE_RATE
    expected_gross = expected_quantity * (120.5 - 110.0)
    assert trade["entry_fee"] == pytest.approx(expected_entry_fee)
    assert trade["exit_fee"] == pytest.approx(expected_exit_fee)
    assert trade["net_pnl"] == pytest.approx(
        expected_gross - expected_entry_fee - expected_exit_fee
    )
    assert metrics["entries"] == 1
    assert metrics["exits"] == 1


def test_reversal_charges_close_and_new_entry() -> None:
    data = execution_fixture()
    data.loc[1, "decision_target"] = -1.0
    data.loc[1, "decision_reason"] = "REVERSE"
    metrics, trades, _ = run_backtest(data)
    assert metrics["reversals"] == 1
    assert metrics["entries"] == 2
    assert metrics["exits"] == 2
    assert len(trades) == 2
    assert (trades["entry_fee"] > 0).all()
    assert (trades["exit_fee"] > 0).all()


def test_no_trade_metrics_are_safe() -> None:
    data = execution_fixture()
    data["decision_target"] = np.nan
    metrics, trades, equity = run_backtest(data)
    assert trades.empty
    assert metrics["total_trades"] == 0
    assert metrics["win_rate"] == 0.0
    assert metrics["sharpe_ratio"] == 0.0
    assert metrics["max_drawdown"] == 0.0
    assert equity["equity"].eq(1_000.0).all()


def test_metric_calculations_match_equity_curve() -> None:
    metrics, _, equity = run_backtest(execution_fixture())
    returns = equity["equity"].pct_change().dropna()
    expected_sharpe = np.sqrt(365.0) * returns.mean() / returns.std(ddof=1)
    expected_drawdown = -(equity["equity"] / equity["equity"].cummax() - 1).min()
    assert metrics["final_equity"] == pytest.approx(equity["equity"].iloc[-1])
    assert metrics["net_return"] == pytest.approx(
        equity["equity"].iloc[-1] / 1_000.0 - 1.0
    )
    assert metrics["sharpe_ratio"] == pytest.approx(expected_sharpe)
    assert metrics["max_drawdown"] == pytest.approx(expected_drawdown)


def test_dataset_validation_rejects_duplicates_and_bad_ohlc(tmp_path: Path) -> None:
    duplicate = ohlcv(4)
    duplicate.loc[1, "datetime"] = duplicate.loc[0, "datetime"]
    path = tmp_path / "duplicate.csv"
    duplicate.to_csv(path, index=False)
    with pytest.raises(ValueError, match="duplicate timestamp"):
        load_dataset(path)

    invalid = ohlcv(4)
    invalid.loc[2, "low"] = invalid.loc[2, "high"] + 1.0
    path = tmp_path / "invalid.csv"
    invalid.to_csv(path, index=False)
    with pytest.raises(ValueError, match="invalid OHLCV row"):
        load_dataset(path)
