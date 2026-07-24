"""Integrity tests for the organizer-compatible SatoshiFlow submission."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

PROJECT_DIR = Path(__file__).resolve().parents[1]
REPOSITORY_DIR = PROJECT_DIR.parent
DATASET_PATH = PROJECT_DIR / "btc_18_22_1d.csv"
SUBMITTED_MAIN = REPOSITORY_DIR / "SUBMIT_THESE" / "main.py"
EXPECTED_BACKTESTER_BLOB = "3b94f9749fb64e4fe271fae28d16628ea9fe2519"
sys.path.insert(0, str(PROJECT_DIR))

from main import (  # noqa: E402
    StrategyConfig,
    assert_reproducible,
    assert_signal_shift,
    calculate_adx,
    calculate_atr,
    calculate_ema,
    execute_organizer_backtest,
    load_dataset,
    process_data,
    run_lookahead_check,
    strat,
    validate_signal_sequence,
)


def ohlcv(rows: int = 300) -> pd.DataFrame:
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


def transition_fixture() -> tuple[pd.DataFrame, StrategyConfig]:
    close = np.array([11.0, 12.0, 13.0, 14.0])
    frame = pd.DataFrame(
        {
            "datetime": pd.date_range("2020-01-01", periods=4, freq="D"),
            "open": close - 0.1,
            "high": close + 0.5,
            "low": close - 0.5,
            "close": close,
            "volume": 1.0,
            "ATR": 1.0,
            "EMA200": 10.0,
            "ADX": 30.0,
            "DI+": 20.0,
            "DI-": 10.0,
            "donchian_high": 10.0,
            "donchian_low": 5.0,
        }
    )
    config = StrategyConfig(
        donchian_period=1,
        adx_period=1,
        adx_threshold=20.0,
        ema_period=1,
        atr_period=1,
        atr_stop_multiplier=2.5,
    )
    return frame, config


def git_blob_hash(path: Path) -> str:
    # Git's text clean filter normalizes the Windows checkout to LF before
    # comparing it with the immutable organizer blob.
    content = path.read_bytes().replace(b"\r\n", b"\n")
    header = f"blob {len(content)}\0".encode()
    return hashlib.sha1(header + content).hexdigest()


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


def test_ema_is_recursive() -> None:
    actual = calculate_ema(pd.Series([10.0, 12.0, 14.0]), period=3)
    assert actual.tolist() == pytest.approx([10.0, 11.0, 12.5])


def test_adx_output_is_sane() -> None:
    data = ohlcv(30)
    adx, plus_di, minus_di = calculate_adx(data, period=3)
    finite_adx = adx.dropna()
    assert not finite_adx.empty
    assert finite_adx.between(0.0, 100.0).all()
    assert plus_di.dropna().between(0.0, 100.0).all()
    assert minus_di.dropna().between(0.0, 100.0).all()


def test_donchian_levels_exclude_current_bar() -> None:
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
    assert changed_result.loc[3, "donchian_high"] == result.loc[
        3, "donchian_high"
    ]


def test_prefix_invariance_at_required_cutoffs() -> None:
    data = load_dataset(DATASET_PATH)
    cutoffs = run_lookahead_check(data)
    assert len(cutoffs) == 5


def test_indicators_do_not_change_when_future_rows_are_appended() -> None:
    data = ohlcv(300)
    full = process_data(data)
    prefix = process_data(data.iloc[:250].copy())
    for column in (
        "ATR",
        "EMA200",
        "ADX",
        "DI+",
        "DI-",
        "donchian_high",
        "donchian_low",
    ):
        pd.testing.assert_series_equal(
            prefix[column], full.loc[:249, column], check_names=False
        )


def test_decision_is_shifted_exactly_one_row() -> None:
    frame, config = transition_fixture()
    result = strat(frame, config, force_close=True)
    assert_signal_shift(result)
    assert result["decision_signal"].tolist() == [0, 1, -1, 0]
    assert result["signals"].tolist() == [0, 0, 1, -1]


def test_no_same_row_decision_execution() -> None:
    frame, config = transition_fixture()
    result = strat(frame, config, force_close=False)
    assert result.loc[1, "decision_signal"] == 1
    assert result.loc[1, "signals"] == 0
    assert result.loc[2, "signals"] == 1


def test_every_signal_is_valid_under_organizer_rules() -> None:
    data = load_dataset(DATASET_PATH)
    result = strat(process_data(data))
    assert validate_signal_sequence(result["signals"]) == 0
    assert set(result["signals"].unique()).issubset({-2, -1, 0, 1, 2})


def test_final_open_position_is_closed_mechanically() -> None:
    frame, config = transition_fixture()
    result = strat(frame, config, force_close=True)
    assert bool(result.loc[2, "forced_liquidation"])
    assert result.loc[2, "decision_reason"] == "END_OF_DATA_LIQUIDATION"
    assert result.loc[3, "signals"] == -1
    assert validate_signal_sequence(result["signals"]) == 0


@pytest.mark.parametrize(
    ("mutator", "message"),
    [
        (
            lambda frame: frame.assign(
                datetime=[
                    frame.loc[0, "datetime"],
                    frame.loc[0, "datetime"],
                    *frame.loc[2:, "datetime"],
                ]
            ),
            "duplicate timestamp",
        ),
        (
            lambda frame: frame.assign(
                low=frame["high"] + 1.0,
            ),
            "invalid OHLCV row",
        ),
        (
            lambda frame: frame.assign(volume=-1.0),
            "invalid OHLCV row",
        ),
    ],
)
def test_dataset_validation_rejects_bad_rows(
    tmp_path: Path, mutator, message: str
) -> None:
    invalid = mutator(ohlcv(4))
    path = tmp_path / "invalid.csv"
    invalid.to_csv(path, index=False)
    with pytest.raises(ValueError, match=message):
        load_dataset(path)


def test_dataset_validation_rejects_missing_columns(tmp_path: Path) -> None:
    path = tmp_path / "missing.csv"
    ohlcv(4).drop(columns="volume").to_csv(path, index=False)
    with pytest.raises(ValueError, match="missing required columns"):
        load_dataset(path)


def test_full_organizer_run_and_reproducibility(tmp_path: Path) -> None:
    data = load_dataset(DATASET_PATH)
    first_signals = strat(process_data(data))
    second_signals = strat(process_data(data))
    pd.testing.assert_frame_equal(first_signals, second_signals)

    signal_path = tmp_path / "signals.csv"
    first_signals.to_csv(signal_path, index=False)
    first = execute_organizer_backtest(signal_path)
    second = execute_organizer_backtest(signal_path)
    assert_reproducible(first, second)
    assert first[1]["total_trades"] > 0


def test_submitted_main_matches_project_main() -> None:
    assert SUBMITTED_MAIN.read_bytes() == (PROJECT_DIR / "main.py").read_bytes()
    assert b"from backtester import BackTester" in SUBMITTED_MAIN.read_bytes()


def test_organizer_backtester_matches_original_blob() -> None:
    assert git_blob_hash(PROJECT_DIR / "backtester.py") == EXPECTED_BACKTESTER_BLOB
