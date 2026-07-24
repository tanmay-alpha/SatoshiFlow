#!/usr/bin/env python3
"""Organizer-compatible SatoshiFlow BTC/USD submission.

The strategy forms each decision from completed candle ``t`` and writes the
corresponding executable signal on candle ``t+1``. The unchanged organizer
backtester therefore executes the shifted signal at candle ``t+1`` close.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from backtester import BackTester


REQUIRED_COLUMNS = ("datetime", "open", "high", "low", "close", "volume")
INITIAL_CAPITAL = 1_000.0
BROKERAGE_RATE = 0.0015
INDICATOR_COLUMNS = (
    "ATR",
    "EMA200",
    "ADX",
    "DI+",
    "DI-",
    "donchian_high",
    "donchian_low",
)


@dataclass(frozen=True)
class StrategyConfig:
    """Fixed parameters selected before the final organizer-framework run."""

    donchian_period: int = 30
    adx_period: int = 14
    adx_threshold: float = 20.0
    ema_period: int = 200
    atr_period: int = 14
    atr_stop_multiplier: float = 2.5


DEFAULT_CONFIG = StrategyConfig()


def true_range(data: pd.DataFrame) -> pd.Series:
    """TR = max(H-L, |H-Cprev|, |L-Cprev|)."""
    previous_close = data["close"].shift(1)
    return pd.concat(
        (
            data["high"] - data["low"],
            (data["high"] - previous_close).abs(),
            (data["low"] - previous_close).abs(),
        ),
        axis=1,
    ).max(axis=1)


def wilder_average(values: pd.Series, period: int) -> pd.Series:
    """Wilder recursive average seeded by the first arithmetic mean."""
    if period <= 0:
        raise ValueError("period must be positive")
    numeric = values.astype(float).to_numpy()
    output = np.full(len(numeric), np.nan, dtype=float)
    if len(numeric) < period:
        return pd.Series(output, index=values.index, dtype=float)
    output[period - 1] = float(np.mean(numeric[:period]))
    for index in range(period, len(numeric)):
        output[index] = output[index - 1] + (
            numeric[index] - output[index - 1]
        ) / period
    return pd.Series(output, index=values.index, dtype=float)


def calculate_atr(data: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average True Range with Wilder smoothing."""
    return wilder_average(true_range(data), period)


def calculate_ema(
    values: pd.Series | pd.DataFrame, period: int = 200
) -> pd.Series:
    """EMA_t = alpha*price_t + (1-alpha)*EMA_(t-1)."""
    source = values["close"] if isinstance(values, pd.DataFrame) else values
    if period <= 0:
        raise ValueError("period must be positive")
    numeric = source.astype(float).to_numpy()
    output = np.full(len(numeric), np.nan, dtype=float)
    if not len(numeric):
        return pd.Series(output, index=source.index, dtype=float)
    alpha = 2.0 / (period + 1.0)
    output[0] = numeric[0]
    for index in range(1, len(numeric)):
        output[index] = (
            alpha * numeric[index] + (1.0 - alpha) * output[index - 1]
        )
    return pd.Series(output, index=source.index, dtype=float)


def calculate_adx(
    data: pd.DataFrame, period: int = 14
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Return ADX, DI+, and DI- from Wilder directional movement."""
    up_move = data["high"].diff()
    down_move = -data["low"].diff()
    plus_dm = pd.Series(
        np.where((up_move > down_move) & (up_move > 0), up_move, 0.0),
        index=data.index,
        dtype=float,
    )
    minus_dm = pd.Series(
        np.where((down_move > up_move) & (down_move > 0), down_move, 0.0),
        index=data.index,
        dtype=float,
    )
    atr = calculate_atr(data, period)
    plus_di = 100.0 * wilder_average(plus_dm, period) / atr
    minus_di = 100.0 * wilder_average(minus_dm, period) / atr
    denominator = plus_di + minus_di
    dx = (100.0 * (plus_di - minus_di).abs() / denominator).where(
        denominator != 0
    )

    adx_values = np.full(len(data), np.nan, dtype=float)
    seed_index = 2 * period - 2
    if len(data) > seed_index:
        seed = dx.iloc[period - 1 : seed_index + 1]
        if seed.notna().any():
            adx_values[seed_index] = float(seed.mean())
            for index in range(seed_index + 1, len(data)):
                current = float(dx.iloc[index])
                if np.isfinite(current):
                    adx_values[index] = (
                        (period - 1) * adx_values[index - 1] + current
                    ) / period
    return (
        pd.Series(adx_values, index=data.index, dtype=float),
        plus_di,
        minus_di,
    )


def process_data(
    data: pd.DataFrame, config: StrategyConfig = DEFAULT_CONFIG
) -> pd.DataFrame:
    """Calculate only indicators used by the submitted strategy.

    Donchian thresholds are shifted one completed bar, so candle ``t`` cannot
    be included in its own breakout level. No series is backfilled and no
    centered rolling window is used.
    """
    result = data.copy().reset_index(drop=True)
    result["ATR"] = calculate_atr(result, config.atr_period)
    result["EMA200"] = calculate_ema(result["close"], config.ema_period)
    result["ADX"], result["DI+"], result["DI-"] = calculate_adx(
        result, config.adx_period
    )
    result["donchian_high"] = (
        result["high"]
        .shift(1)
        .rolling(
            config.donchian_period,
            min_periods=config.donchian_period,
        )
        .max()
    )
    result["donchian_low"] = (
        result["low"]
        .shift(1)
        .rolling(
            config.donchian_period,
            min_periods=config.donchian_period,
        )
        .min()
    )
    return result


def _signal_for_transition(current: int, target: int) -> int:
    """Encode a target-position change in the organizer signal convention."""
    if current == 0 and target in (-1, 1):
        return target
    if current == 1 and target == 0:
        return -1
    if current == -1 and target == 0:
        return 1
    if current == 1 and target == -1:
        return -2
    if current == -1 and target == 1:
        return 2
    raise ValueError(f"unsupported position transition: {current} -> {target}")


def strat(
    data: pd.DataFrame,
    config: StrategyConfig = DEFAULT_CONFIG,
    *,
    force_close: bool = True,
) -> pd.DataFrame:
    """Generate deterministic, one-row-shifted organizer signals.

    A decision is formed after completed candle ``t``. It is stored in
    ``decision_signal[t]`` and copied to ``signals[t+1]``. The organizer
    framework consequently executes at candle ``t+1`` close, never on the
    decision candle.

    The trailing stop uses the most favorable high/low observed after entry.
    Because an entry executes at a candle close, its initial extremum is that
    execution close; subsequent completed candles contribute highs/lows.

    For backtest completeness, a position still open at the penultimate row is
    assigned a mechanical close decision for the final row. This boundary
    liquidation is separate from the economic strategy.
    """
    result = data.copy().reset_index(drop=True)
    result["signals"] = 0
    result["decision_signal"] = 0
    result["decision_target"] = np.nan
    result["decision_reason"] = "HOLD"
    result["trade_type"] = "HOLD"
    result["forced_liquidation"] = False

    position = 0
    pending_target: int | None = None
    pending_signal = 0
    pending_reason = "HOLD"
    highest_since_entry = -math.inf
    lowest_since_entry = math.inf
    trailing_stop = math.nan
    warmup = max(
        config.ema_period - 1,
        2 * config.adx_period - 2,
        config.donchian_period,
        config.atr_period - 1,
    )

    for index in range(len(result)):
        row = result.iloc[index]
        entered_this_row = False

        # Execute only the decision formed on the previous completed candle.
        if pending_target is not None:
            old_position = position
            result.at[index, "signals"] = pending_signal
            result.at[index, "trade_type"] = pending_reason
            position = pending_target
            entered_this_row = position != 0 and position != old_position
            if entered_this_row:
                execution_close = float(row["close"])
                highest_since_entry = execution_close
                lowest_since_entry = execution_close
                atr = float(row["ATR"])
                trailing_stop = (
                    execution_close
                    - config.atr_stop_multiplier * atr
                    if position == 1
                    else execution_close
                    + config.atr_stop_multiplier * atr
                )
            elif position == 0:
                highest_since_entry = -math.inf
                lowest_since_entry = math.inf
                trailing_stop = math.nan
            pending_target = None
            pending_signal = 0
            pending_reason = "HOLD"

        # Production discards a last-row decision because it has no execution
        # row. The no-boundary lookahead mode still records that economic
        # decision so it can be compared with the same row in a longer prefix.
        if force_close and index == len(result) - 1:
            continue
        if index < warmup:
            continue

        required = [float(row[column]) for column in INDICATOR_COLUMNS]
        if not all(np.isfinite(value) for value in required):
            continue

        long_breakout = (
            row["close"] > row["donchian_high"]
            and row["close"] > row["EMA200"]
            and row["ADX"] >= config.adx_threshold
            and row["DI+"] > row["DI-"]
        )
        short_breakout = (
            row["close"] < row["donchian_low"]
            and row["close"] < row["EMA200"]
            and row["ADX"] >= config.adx_threshold
            and row["DI-"] > row["DI+"]
        )

        if position == 1:
            if not entered_this_row:
                highest_since_entry = max(
                    highest_since_entry, float(row["high"])
                )
                trailing_stop = max(
                    trailing_stop,
                    highest_since_entry
                    - config.atr_stop_multiplier * float(row["ATR"]),
                )
        elif position == -1:
            if not entered_this_row:
                lowest_since_entry = min(
                    lowest_since_entry, float(row["low"])
                )
                trailing_stop = min(
                    trailing_stop,
                    lowest_since_entry
                    + config.atr_stop_multiplier * float(row["ATR"]),
                )

        target: int | None = None
        reason = "HOLD"
        if position == 0:
            if long_breakout:
                target, reason = 1, "LONG_BREAKOUT"
            elif short_breakout:
                target, reason = -1, "SHORT_BREAKOUT"
        elif position == 1:
            if short_breakout:
                target, reason = -1, "REVERSE_TO_SHORT"
            elif row["close"] <= trailing_stop:
                target, reason = 0, "LONG_ATR_STOP"
        else:
            if long_breakout:
                target, reason = 1, "REVERSE_TO_LONG"
            elif row["close"] >= trailing_stop:
                target, reason = 0, "SHORT_ATR_STOP"

        # Boundary-only liquidation: execute a valid close on the final row.
        if force_close and index == len(result) - 2:
            if position != 0:
                target, reason = 0, "END_OF_DATA_LIQUIDATION"
                result.at[index, "forced_liquidation"] = True
            else:
                target = None  # Never open a trade that can only exist one row.

        if target is not None and target != position:
            decision_signal = _signal_for_transition(position, target)
            result.at[index, "decision_signal"] = decision_signal
            result.at[index, "decision_target"] = target
            result.at[index, "decision_reason"] = reason
            pending_target = target
            pending_signal = decision_signal
            pending_reason = reason

    return result


def validate_signal_sequence(signals: pd.Series) -> int:
    """Replay organizer position rules; return the final position."""
    position = 0
    for index, raw_signal in enumerate(signals):
        signal = int(raw_signal)
        if signal not in (-2, -1, 0, 1, 2):
            raise AssertionError(f"invalid signal value {signal} at row {index}")
        if position == 0:
            if abs(signal) > 1:
                raise AssertionError(
                    f"reversal signal {signal} while flat at row {index}"
                )
            if signal != 0:
                position = 1 if signal > 0 else -1
        elif position == 1:
            if signal > 0:
                raise AssertionError(
                    f"same-direction signal {signal} while long at row {index}"
                )
            if signal == -1:
                position = 0
            elif signal == -2:
                position = -1
        else:
            if signal < 0:
                raise AssertionError(
                    f"same-direction signal {signal} while short at row {index}"
                )
            if signal == 1:
                position = 0
            elif signal == 2:
                position = 1
    return position


def assert_signal_shift(result: pd.DataFrame) -> None:
    """Assert decisions are executable exactly one row later."""
    assert int(result["signals"].iloc[0]) == 0
    expected = result["decision_signal"].iloc[:-1].astype(int).to_numpy()
    actual = result["signals"].iloc[1:].astype(int).to_numpy()
    np.testing.assert_array_equal(actual, expected)
    assert int(result["decision_signal"].iloc[-1]) == 0


def run_lookahead_check(
    raw_data: pd.DataFrame,
    config: StrategyConfig = DEFAULT_CONFIG,
) -> list[int]:
    """Check indicator and economic-signal prefix invariance at five cutoffs.

    Mechanical end-of-file liquidation is disabled here because a prefix has a
    different artificial boundary. Its validity is tested independently.
    """
    full_indicators = process_data(raw_data, config)
    full_signals = strat(full_indicators, config, force_close=False)
    warmup = max(
        config.ema_period - 1,
        2 * config.adx_period - 2,
        config.donchian_period,
        config.atr_period - 1,
    )
    candidates = (
        warmup + 5,
        len(raw_data) // 4,
        len(raw_data) // 2,
        3 * len(raw_data) // 4,
        len(raw_data) - 3,
    )
    cutoffs = sorted(
        {cutoff for cutoff in candidates if warmup < cutoff < len(raw_data)}
    )
    for cutoff in cutoffs:
        prefix = raw_data.iloc[: cutoff + 1].copy()
        prefix_indicators = process_data(prefix, config)
        prefix_signals = strat(
            prefix_indicators, config, force_close=False
        )
        for column in INDICATOR_COLUMNS:
            pd.testing.assert_series_equal(
                prefix_indicators[column],
                full_indicators.loc[:cutoff, column],
                check_names=False,
            )
        pd.testing.assert_series_equal(
            prefix_signals["decision_signal"],
            full_signals.loc[:cutoff, "decision_signal"],
            check_names=False,
        )
        pd.testing.assert_series_equal(
            prefix_signals["signals"],
            full_signals.loc[:cutoff, "signals"],
            check_names=False,
        )
    return cutoffs


def dataset_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1_048_576), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_dataset(path: Path) -> pd.DataFrame:
    """Load, sort, and strictly validate the OHLCV challenge schema."""
    data = pd.read_csv(path)
    missing = [column for column in REQUIRED_COLUMNS if column not in data]
    if missing:
        raise ValueError(f"missing required columns: {', '.join(missing)}")
    data = data.loc[:, REQUIRED_COLUMNS].copy()
    data["datetime"] = pd.to_datetime(data["datetime"], errors="raise")
    for column in REQUIRED_COLUMNS[1:]:
        data[column] = pd.to_numeric(data[column], errors="raise")
    data = data.sort_values("datetime", kind="mergesort").reset_index(drop=True)
    if data["datetime"].duplicated().any():
        duplicate = data.loc[data["datetime"].duplicated(), "datetime"].iloc[0]
        raise ValueError(f"duplicate timestamp: {duplicate}")
    if data.isna().any().any():
        raise ValueError("dataset contains missing values")
    invalid = (
        (data["low"] > data["high"])
        | (data["open"] < data["low"])
        | (data["open"] > data["high"])
        | (data["close"] < data["low"])
        | (data["close"] > data["high"])
        | (data[["open", "high", "low", "close"]] <= 0).any(axis=1)
        | (data["volume"] < 0)
    )
    if invalid.any():
        raise ValueError(f"invalid OHLCV row at index {int(invalid.idxmax())}")
    return data


def resolve_dataset(requested: str | None) -> Path:
    """Resolve explicit path, official filename, then repository fallback."""
    script_dir = Path(__file__).resolve().parent
    if requested:
        supplied = Path(requested).expanduser()
        candidates = (
            (supplied,)
            if supplied.is_absolute()
            else (Path.cwd() / supplied, script_dir / supplied)
        )
        for candidate in candidates:
            if candidate.exists():
                return candidate.resolve()
        raise FileNotFoundError(f"dataset not found: {requested}")
    for name in ("BTC_2019_2023_1d.csv", "btc_18_22_1d.csv"):
        for candidate in (Path.cwd() / name, script_dir / name):
            if candidate.exists():
                return candidate.resolve()
    raise FileNotFoundError(
        "no dataset found; pass --data or add BTC_2019_2023_1d.csv "
        "or btc_18_22_1d.csv beside main.py"
    )


def _trade_rows(bt: BackTester) -> pd.DataFrame:
    rows = []
    for trade in bt.trades:
        brokerage = BROKERAGE_RATE * abs(float(trade.qty))
        rows.append(
            {
                "direction": str(trade.trade_type()),
                "entry_time": trade.init_timestamp,
                "exit_time": trade.final_timestamp,
                "entry_price": float(trade.init_price),
                "exit_price": float(trade.final_price),
                "quantity_usd": float(trade.qty),
                "brokerage": brokerage,
                "net_pnl": float(trade.pnl()),
                "holding_time": str(trade.holding_time()),
            }
        )
    return pd.DataFrame(
        rows,
        columns=(
            "direction",
            "entry_time",
            "exit_time",
            "entry_price",
            "exit_price",
            "quantity_usd",
            "brokerage",
            "net_pnl",
            "holding_time",
        ),
    )


def _normalized_stats(stats: dict[str, Any] | None) -> dict[str, float | int]:
    stats = stats or {}
    return {
        "total_trades": int(stats.get("Total Trades", 0)),
        "net_profit": float(stats.get("Net Profit", 0.0)),
        "sharpe_ratio": float(stats.get("Sharpe Ratio", 0.0)),
        "maximum_drawdown_percentage": float(
            stats.get("Maximum Drawdown(%)", 0.0)
        ),
        "win_rate_percentage": float(stats.get("Win Rate", 0.0)),
        "benchmark_return_percentage": float(
            stats.get("Benchmark Return(%)", 0.0)
        ),
    }


def execute_organizer_backtest(
    signal_path: Path,
) -> tuple[BackTester, dict[str, float | int], pd.DataFrame]:
    """Run the unchanged organizer framework using its normal public API."""
    bt = BackTester(
        "BTC",
        signal_data_path=str(signal_path),
        master_file_path=str(signal_path),
        compound_flag=1,
    )
    bt.get_trades(1000)
    stats = _normalized_stats(bt.get_statistics())
    if "capital" not in bt.data:
        bt.calc_capital()
    return bt, stats, _trade_rows(bt)


def assert_reproducible(
    first: tuple[BackTester, dict[str, float | int], pd.DataFrame],
    second: tuple[BackTester, dict[str, float | int], pd.DataFrame],
) -> None:
    first_bt, first_stats, first_trades = first
    second_bt, second_stats, second_trades = second
    assert json.dumps(first_stats, sort_keys=True) == json.dumps(
        second_stats, sort_keys=True
    )
    pd.testing.assert_frame_equal(first_trades, second_trades)
    pd.testing.assert_series_equal(
        first_bt.data["capital"],
        second_bt.data["capital"],
        check_names=False,
    )


def build_metrics(
    dataset_path: Path,
    data: pd.DataFrame,
    stats: dict[str, float | int],
    trades: pd.DataFrame,
    cutoffs: list[int],
    forced_final_liquidation: bool,
) -> dict[str, Any]:
    net_profit = float(stats["net_profit"])
    return {
        "dataset_filename": dataset_path.name,
        "dataset_sha256": dataset_hash(dataset_path),
        "dataset_row_count": int(len(data)),
        "dataset_first_date": data["datetime"].iloc[0].isoformat(),
        "dataset_last_date": data["datetime"].iloc[-1].isoformat(),
        "parameters": asdict(DEFAULT_CONFIG),
        "initial_capital": INITIAL_CAPITAL,
        "brokerage_rate": BROKERAGE_RATE,
        "brokerage_model": (
            "Organizer TradePair.pnl deducts 0.15% of absolute trade quantity "
            "once per completed trade."
        ),
        "execution_model": (
            "Decision on completed candle t is shifted to candle t+1; "
            "organizer backtester executes at candle t+1 close."
        ),
        "total_trades": int(stats["total_trades"]),
        "net_profit": net_profit,
        "final_capital": INITIAL_CAPITAL + net_profit,
        "net_return": net_profit / INITIAL_CAPITAL,
        "sharpe_ratio": float(stats["sharpe_ratio"]),
        "maximum_drawdown_percentage": float(
            stats["maximum_drawdown_percentage"]
        ),
        "win_rate_percentage": float(stats["win_rate_percentage"]),
        "benchmark_return_percentage": float(
            stats["benchmark_return_percentage"]
        ),
        "total_brokerage": (
            float(trades["brokerage"].sum()) if len(trades) else 0.0
        ),
        "lookahead_check": True,
        "signal_shift_check": True,
        "signal_validity_check": True,
        "organizer_backtester_check": True,
        "reproducibility_check": True,
        "lookahead_cutoffs": cutoffs,
        "forced_final_liquidation": forced_final_liquidation,
    }


def write_outputs(
    results_dir: Path,
    result_data: pd.DataFrame,
    bt: BackTester,
    trades: pd.DataFrame,
    metrics: dict[str, Any],
) -> None:
    results_dir.mkdir(parents=True, exist_ok=True)
    signal_path = results_dir / "signals.csv"
    result_data.to_csv(signal_path, index=False, float_format="%.10f")
    trades.to_csv(
        results_dir / "trades.csv", index=False, float_format="%.10f"
    )
    (results_dir / "metrics.json").write_text(
        json.dumps(metrics, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )

    figure, price_axis = plt.subplots(figsize=(10, 5.5))
    capital_axis = price_axis.twinx()
    price_axis.plot(
        bt.data.index,
        bt.data["close"],
        color="#98A2B3",
        linewidth=1.0,
        label="BTC close",
    )
    capital_axis.plot(
        bt.data.index,
        bt.data["capital"],
        color="#155EEF",
        linewidth=1.7,
        label="Organizer capital",
    )
    price_axis.set_xlabel("Date")
    price_axis.set_ylabel("BTC/USD", color="#667085")
    capital_axis.set_ylabel("Capital (USD)", color="#155EEF")
    price_axis.grid(alpha=0.2)
    figure.suptitle("SatoshiFlow Organizer-Framework Equity")
    figure.tight_layout()
    figure.savefig(results_dir / "equity_curve.png", dpi=160)
    plt.close(figure)

    summary = [
        "SATOSHIFLOW ORGANIZER-FRAMEWORK BACKTEST",
        f"Dataset: {metrics['dataset_filename']}",
        f"SHA-256: {metrics['dataset_sha256']}",
        (
            f"Range: {metrics['dataset_first_date']} to "
            f"{metrics['dataset_last_date']}"
        ),
        f"Initial capital: ${metrics['initial_capital']:.2f}",
        f"Brokerage rate: {100 * metrics['brokerage_rate']:.4f}%",
        f"Total trades: {metrics['total_trades']}",
        f"Net profit: ${metrics['net_profit']:.6f}",
        f"Final capital: ${metrics['final_capital']:.6f}",
        f"Net return: {100 * metrics['net_return']:.6f}%",
        f"Sharpe ratio: {metrics['sharpe_ratio']:.6f}",
        (
            "Maximum drawdown: "
            f"{metrics['maximum_drawdown_percentage']:.6f}%"
        ),
        f"Win rate: {metrics['win_rate_percentage']:.6f}%",
        (
            "Benchmark return: "
            f"{metrics['benchmark_return_percentage']:.6f}%"
        ),
        "LOOKAHEAD CHECK: PASS",
        "SIGNAL SHIFT CHECK: PASS",
        "ORGANIZER BACKTESTER CHECK: PASS",
        "REPRODUCIBILITY CHECK: PASS",
    ]
    (results_dir / "backtest_summary.txt").write_text(
        "\n".join(summary) + "\n", encoding="utf-8"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", help="path to an OHLCV CSV")
    parser.add_argument(
        "--results-dir",
        help="default: results/organizer beside this file",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    dataset_path = resolve_dataset(args.data)
    results_dir = (
        Path(args.results_dir).resolve()
        if args.results_dir
        else Path(__file__).resolve().parent / "results" / "organizer"
    )
    data = load_dataset(dataset_path)
    processed = process_data(data, DEFAULT_CONFIG)
    result_data = strat(processed, DEFAULT_CONFIG, force_close=True)

    assert_signal_shift(result_data)
    final_position = validate_signal_sequence(result_data["signals"])
    assert final_position == 0, "final position was not closed"
    cutoffs = run_lookahead_check(data, DEFAULT_CONFIG)

    results_dir.mkdir(parents=True, exist_ok=True)
    signal_path = results_dir / "signals.csv"
    result_data.to_csv(signal_path, index=False, float_format="%.10f")
    first = execute_organizer_backtest(signal_path)
    second = execute_organizer_backtest(signal_path)
    assert_reproducible(first, second)
    bt, stats, trades = first
    assert int(stats["total_trades"]) == len(trades)

    metrics = build_metrics(
        dataset_path,
        data,
        stats,
        trades,
        cutoffs,
        bool(result_data["forced_liquidation"].any()),
    )
    write_outputs(results_dir, result_data, bt, trades, metrics)

    print(f"Dataset: {dataset_path.name}")
    print(f"Rows: {len(data)}")
    print(f"First date: {data['datetime'].iloc[0].isoformat()}")
    print(f"Last date: {data['datetime'].iloc[-1].isoformat()}")
    print(f"SHA-256: {metrics['dataset_sha256']}")
    print(f"Parameters: {json.dumps(asdict(DEFAULT_CONFIG), sort_keys=True)}")
    print(f"Initial capital: ${INITIAL_CAPITAL:.2f}")
    print(f"Brokerage: {100 * BROKERAGE_RATE:.4f}% per organizer trade")
    print(f"Total trades: {metrics['total_trades']}")
    print(f"Net profit: ${metrics['net_profit']:.6f}")
    print(f"Final capital: ${metrics['final_capital']:.6f}")
    print(f"Sharpe ratio: {metrics['sharpe_ratio']:.6f}")
    print(
        "Maximum drawdown: "
        f"{metrics['maximum_drawdown_percentage']:.6f}%"
    )
    print(f"Win rate: {metrics['win_rate_percentage']:.6f}%")
    print(
        "Benchmark return: "
        f"{metrics['benchmark_return_percentage']:.6f}%"
    )
    print("LOOKAHEAD CHECK: PASS")
    print("SIGNAL SHIFT CHECK: PASS")
    print("ORGANIZER BACKTESTER CHECK: PASS")
    print("REPRODUCIBILITY CHECK: PASS")
    print(f"Results: {results_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
