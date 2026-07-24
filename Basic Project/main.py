#!/usr/bin/env python3
"""Bias-free BTC/USD strategy, execution simulator, and reproducible CLI.

The organizer-provided ``backtester.py`` is intentionally not imported or
modified because its original implementation executes signals at the current
bar close and charges only one side of brokerage. This module preserves the
required ``process_data`` and ``strat`` entry points while using an explicit
next-open, mark-to-market simulator for verified local results.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import warnings
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


REQUIRED_COLUMNS = ("datetime", "open", "high", "low", "close", "volume")
INITIAL_CAPITAL = 1_000.0
BROKERAGE_RATE = 0.0015


@dataclass(frozen=True)
class StrategyConfig:
    """Fixed, deliberately small strategy configuration."""

    donchian_period: int = 30
    adx_period: int = 14
    adx_threshold: float = 20.0
    ema_period: int = 200
    atr_period: int = 14
    atr_stop_multiplier: float = 2.5


DEFAULT_CONFIG = StrategyConfig()


def true_range(data: pd.DataFrame) -> pd.Series:
    """True Range = max(H-L, |H-Cprev|, |L-Cprev|)."""
    previous_close = data["close"].shift(1)
    parts = pd.concat(
        [
            data["high"] - data["low"],
            (data["high"] - previous_close).abs(),
            (data["low"] - previous_close).abs(),
        ],
        axis=1,
    )
    return parts.max(axis=1)


def wilder_average(values: pd.Series, period: int) -> pd.Series:
    """Wilder average seeded by the first arithmetic mean."""
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
    """Average True Range using Wilder smoothing."""
    return wilder_average(true_range(data), period)


def calculate_ema(values: pd.Series | pd.DataFrame, period: int = 200) -> pd.Series:
    """EMA computed recursively with alpha = 2 / (period + 1)."""
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
        output[index] = alpha * numeric[index] + (1.0 - alpha) * output[index - 1]
    return pd.Series(output, index=source.index, dtype=float)


def calculate_adx(
    data: pd.DataFrame, period: int = 14
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Return ADX, DI+, and DI- using Wilder's directional-movement formulas."""
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
                current_dx = float(dx.iloc[index])
                if np.isfinite(current_dx):
                    adx_values[index] = (
                        (period - 1) * adx_values[index - 1] + current_dx
                    ) / period
    return (
        pd.Series(adx_values, index=data.index, dtype=float),
        plus_di,
        minus_di,
    )


def process_data(
    data: pd.DataFrame, config: StrategyConfig = DEFAULT_CONFIG
) -> pd.DataFrame:
    """Calculate only the indicators used by the strategy.

    Donchian levels are shifted by one bar. Therefore the level visible on bar
    ``t`` contains highs/lows through ``t-1`` and cannot include the breakout
    candle itself.
    """
    result = data.copy()
    result["true_range"] = true_range(result)
    result["atr"] = calculate_atr(result, config.atr_period)
    result["ema_regime"] = calculate_ema(result["close"], config.ema_period)
    result["adx"], result["di_plus"], result["di_minus"] = calculate_adx(
        result, config.adx_period
    )
    result["donchian_high"] = (
        result["high"]
        .shift(1)
        .rolling(config.donchian_period, min_periods=config.donchian_period)
        .max()
    )
    result["donchian_low"] = (
        result["low"]
        .shift(1)
        .rolling(config.donchian_period, min_periods=config.donchian_period)
        .min()
    )
    return result


def _signal_for_transition(current: int, target: int) -> int:
    if current == 0:
        return target
    if current == 1 and target == 0:
        return -1
    if current == -1 and target == 0:
        return 1
    if current == 1 and target == -1:
        return -2
    if current == -1 and target == 1:
        return 2
    raise ValueError(f"unsupported transition {current} -> {target}")


def strat(
    data: pd.DataFrame,
    config: StrategyConfig = DEFAULT_CONFIG,
    start_index: int = 0,
) -> pd.DataFrame:
    """Form end-of-bar decisions for execution at the *next* bar open.

    Entry hypothesis:
      * go long on a prior-window Donchian high breakout when ADX confirms
        trend strength, DI+ confirms direction, and price is above its EMA;
      * use the symmetric conditions for shorts.

    Exit/reversal hypothesis:
      * trail the most favorable high/low by ``ATR * multiplier``;
      * reverse only on a confirmed opposite breakout.

    ``decision_target`` is NaN on hold bars and -1/0/+1 when a new target is
    formed. ``signals`` retains the organizer's -2..+2 signal convention.
    """
    result = data.copy()
    result["signals"] = 0
    result["decision_target"] = np.nan
    result["decision_reason"] = "HOLD"

    position = 0
    pending_target: int | None = None
    highest_since_entry = -math.inf
    lowest_since_entry = math.inf
    trailing_stop = math.nan

    warmup = max(
        config.ema_period - 1,
        2 * config.adx_period - 2,
        config.donchian_period,
        config.atr_period - 1,
    )
    first = max(start_index, warmup)

    for index in range(first, len(result)):
        # A target formed on t-1 becomes the position at the open of t.
        if pending_target is not None:
            if pending_target != position:
                position = pending_target
                highest_since_entry = -math.inf
                lowest_since_entry = math.inf
                trailing_stop = math.nan
            pending_target = None

        row = result.iloc[index]
        needed = (
            row["atr"],
            row["adx"],
            row["di_plus"],
            row["di_minus"],
            row["ema_regime"],
            row["donchian_high"],
            row["donchian_low"],
        )
        if not all(np.isfinite(value) for value in needed):
            continue

        long_breakout = (
            row["close"] > row["donchian_high"]
            and row["close"] > row["ema_regime"]
            and row["adx"] >= config.adx_threshold
            and row["di_plus"] > row["di_minus"]
        )
        short_breakout = (
            row["close"] < row["donchian_low"]
            and row["close"] < row["ema_regime"]
            and row["adx"] >= config.adx_threshold
            and row["di_minus"] > row["di_plus"]
        )

        target: int | None = None
        reason = "HOLD"
        if position == 0:
            if long_breakout:
                target, reason = 1, "LONG_BREAKOUT"
            elif short_breakout:
                target, reason = -1, "SHORT_BREAKOUT"
        elif position == 1:
            highest_since_entry = max(highest_since_entry, float(row["high"]))
            candidate = highest_since_entry - config.atr_stop_multiplier * float(
                row["atr"]
            )
            trailing_stop = (
                candidate if not np.isfinite(trailing_stop) else max(trailing_stop, candidate)
            )
            if short_breakout:
                target, reason = -1, "REVERSE_TO_SHORT"
            elif row["close"] <= trailing_stop:
                target, reason = 0, "LONG_ATR_STOP"
        else:
            lowest_since_entry = min(lowest_since_entry, float(row["low"]))
            candidate = lowest_since_entry + config.atr_stop_multiplier * float(
                row["atr"]
            )
            trailing_stop = (
                candidate if not np.isfinite(trailing_stop) else min(trailing_stop, candidate)
            )
            if long_breakout:
                target, reason = 1, "REVERSE_TO_LONG"
            elif row["close"] >= trailing_stop:
                target, reason = 0, "SHORT_ATR_STOP"

        if target is not None and target != position:
            result.iat[index, result.columns.get_loc("signals")] = (
                _signal_for_transition(position, target)
            )
            result.iat[index, result.columns.get_loc("decision_target")] = target
            result.iat[index, result.columns.get_loc("decision_reason")] = reason
            pending_target = target

    return result


@dataclass
class _OpenTrade:
    direction: int
    entry_time: pd.Timestamp
    entry_price: float
    quantity: float
    entry_notional: float
    entry_fee: float
    equity_before_entry: float
    entry_reason: str


def _empty_trades() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "direction",
            "entry_time",
            "exit_time",
            "entry_price",
            "exit_price",
            "quantity",
            "entry_notional",
            "exit_notional",
            "entry_fee",
            "exit_fee",
            "brokerage",
            "gross_pnl",
            "net_pnl",
            "return_pct",
            "holding_days",
            "entry_reason",
            "exit_reason",
            "forced_exit",
        ]
    )


def run_backtest(
    signal_data: pd.DataFrame,
    initial_capital: float = INITIAL_CAPITAL,
    brokerage_rate: float = BROKERAGE_RATE,
) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame]:
    """Execute decisions one bar later at open with daily mark-to-market equity."""
    if initial_capital <= 0:
        raise ValueError("initial_capital must be positive")
    if brokerage_rate < 0:
        raise ValueError("brokerage_rate cannot be negative")
    if signal_data.empty:
        raise ValueError("cannot backtest an empty dataset")

    cash = float(initial_capital)
    quantity = 0.0
    open_trade: _OpenTrade | None = None
    pending_target: int | None = None
    pending_reason = ""
    trade_rows: list[dict[str, Any]] = []
    equity_rows: list[dict[str, Any]] = []
    entries = exits = reversals = 0

    def equity_at(price: float) -> float:
        return cash + quantity * price

    def open_position(
        target: int, price: float, timestamp: pd.Timestamp, reason: str
    ) -> None:
        nonlocal cash, quantity, open_trade, entries
        equity = cash
        if equity <= 0:
            raise RuntimeError("equity is non-positive; cannot open another trade")
        # Fully deploy equity while reserving the entry brokerage.
        notional = equity / (1.0 + brokerage_rate)
        fee = notional * brokerage_rate
        absolute_quantity = notional / price
        quantity = target * absolute_quantity
        if target == 1:
            cash -= notional + fee
        else:
            cash += notional - fee
        open_trade = _OpenTrade(
            direction=target,
            entry_time=timestamp,
            entry_price=price,
            quantity=absolute_quantity,
            entry_notional=notional,
            entry_fee=fee,
            equity_before_entry=equity,
            entry_reason=reason,
        )
        entries += 1

    def close_position(
        price: float, timestamp: pd.Timestamp, reason: str, forced: bool
    ) -> None:
        nonlocal cash, quantity, open_trade, exits
        if open_trade is None:
            return
        exit_notional = open_trade.quantity * price
        exit_fee = exit_notional * brokerage_rate
        if open_trade.direction == 1:
            cash += exit_notional - exit_fee
        else:
            cash -= exit_notional + exit_fee
        gross_pnl = (
            open_trade.direction
            * open_trade.quantity
            * (price - open_trade.entry_price)
        )
        net_pnl = gross_pnl - open_trade.entry_fee - exit_fee
        trade_rows.append(
            {
                "direction": "LONG" if open_trade.direction == 1 else "SHORT",
                "entry_time": open_trade.entry_time,
                "exit_time": timestamp,
                "entry_price": open_trade.entry_price,
                "exit_price": price,
                "quantity": open_trade.quantity,
                "entry_notional": open_trade.entry_notional,
                "exit_notional": exit_notional,
                "entry_fee": open_trade.entry_fee,
                "exit_fee": exit_fee,
                "brokerage": open_trade.entry_fee + exit_fee,
                "gross_pnl": gross_pnl,
                "net_pnl": net_pnl,
                "return_pct": 100.0
                * net_pnl
                / open_trade.equity_before_entry,
                "holding_days": (
                    timestamp - open_trade.entry_time
                ).total_seconds()
                / 86_400.0,
                "entry_reason": open_trade.entry_reason,
                "exit_reason": reason,
                "forced_exit": forced,
            }
        )
        quantity = 0.0
        open_trade = None
        exits += 1

    for offset, (_, row) in enumerate(signal_data.iterrows()):
        timestamp = pd.Timestamp(row["datetime"])
        open_price = float(row["open"])
        close_price = float(row["close"])

        # The only execution point for a decision formed on the prior candle.
        if pending_target is not None:
            current = 0 if open_trade is None else open_trade.direction
            if pending_target != current:
                reversing = current != 0 and pending_target != 0
                if current != 0:
                    close_position(open_price, timestamp, pending_reason, False)
                if pending_target != 0:
                    open_position(
                        pending_target, open_price, timestamp, pending_reason
                    )
                if reversing:
                    reversals += 1
            pending_target = None

        is_last = offset == len(signal_data) - 1
        if is_last and open_trade is not None:
            close_position(close_price, timestamp, "FINAL_BAR_FORCE_CLOSE", True)

        equity = equity_at(close_price)
        equity_rows.append(
            {
                "datetime": timestamp,
                "equity": equity,
                "cash": cash,
                "position": 0 if open_trade is None else open_trade.direction,
                "close": close_price,
            }
        )

        decision = row.get("decision_target", np.nan)
        if not is_last and pd.notna(decision):
            pending_target = int(decision)
            pending_reason = str(row.get("decision_reason", "SIGNAL"))

    trades = pd.DataFrame(trade_rows) if trade_rows else _empty_trades()
    equity_curve = pd.DataFrame(equity_rows)
    returns = equity_curve["equity"].pct_change().dropna()
    volatility = float(returns.std(ddof=1)) if len(returns) > 1 else 0.0
    sharpe = (
        math.sqrt(365.0) * float(returns.mean()) / volatility
        if volatility > 0
        else 0.0
    )
    running_max = equity_curve["equity"].cummax()
    drawdown = equity_curve["equity"] / running_max - 1.0
    equity_curve["daily_return"] = equity_curve["equity"].pct_change().fillna(0.0)
    equity_curve["drawdown"] = drawdown.fillna(0.0)

    net_pnls = trades["net_pnl"].astype(float) if len(trades) else pd.Series(dtype=float)
    gross_pnls = (
        trades["gross_pnl"].astype(float) if len(trades) else pd.Series(dtype=float)
    )
    wins = net_pnls[net_pnls > 0]
    losses = net_pnls[net_pnls <= 0]
    profit_factor: float | None = (
        float(wins.sum() / abs(losses.sum()))
        if len(losses) and losses.sum() < 0
        else (None if len(wins) else 0.0)
    )
    final_equity = float(equity_curve["equity"].iloc[-1])
    first_open = float(signal_data["open"].iloc[0])
    final_close = float(signal_data["close"].iloc[-1])

    metrics: dict[str, Any] = {
        "initial_capital": float(initial_capital),
        "brokerage_rate": float(brokerage_rate),
        "final_equity": final_equity,
        "net_profit": final_equity - initial_capital,
        "net_return": final_equity / initial_capital - 1.0,
        "sharpe_ratio": float(sharpe),
        "max_drawdown": float(-drawdown.min()),
        "win_rate": float(100.0 * len(wins) / len(trades)) if len(trades) else 0.0,
        "total_trades": int(len(trades)),
        "average_trade": float(net_pnls.mean()) if len(trades) else 0.0,
        "profit_factor": profit_factor,
        "buy_and_hold_return": final_close / first_open - 1.0,
        "entries": int(entries),
        "exits": int(exits),
        "reversals": int(reversals),
        "total_brokerage": float(trades["brokerage"].sum()) if len(trades) else 0.0,
        "gross_profit": float(gross_pnls.sum()) if len(trades) else 0.0,
    }
    return metrics, trades, equity_curve


def dataset_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1_048_576), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_dataset(path: Path) -> pd.DataFrame:
    """Load and strictly validate the challenge OHLCV schema."""
    data = pd.read_csv(path)
    missing = [column for column in REQUIRED_COLUMNS if column not in data.columns]
    if missing:
        raise ValueError(f"missing required columns: {', '.join(missing)}")
    data = data.loc[:, REQUIRED_COLUMNS].copy()
    data["datetime"] = pd.to_datetime(data["datetime"], errors="raise")
    for column in REQUIRED_COLUMNS[1:]:
        data[column] = pd.to_numeric(data[column], errors="raise")
    data = data.sort_values("datetime", kind="mergesort").reset_index(drop=True)
    if data["datetime"].duplicated().any():
        duplicated = data.loc[data["datetime"].duplicated(), "datetime"].iloc[0]
        raise ValueError(f"duplicate timestamp: {duplicated}")
    if data.isna().any().any():
        raise ValueError("dataset contains missing values")
    invalid = (
        (data["low"] > data["high"])
        | (data["open"] < data["low"])
        | (data["open"] > data["high"])
        | (data["close"] < data["low"])
        | (data["close"] > data["high"])
        | (data[["open", "high", "low", "close", "volume"]] <= 0).any(axis=1)
    )
    if invalid.any():
        raise ValueError(f"invalid OHLCV row at index {int(invalid.idxmax())}")
    return data


def resolve_dataset(requested: str | None) -> Path:
    script_dir = Path(__file__).resolve().parent
    if requested:
        candidate = Path(requested).expanduser()
        if not candidate.is_absolute() and not candidate.exists():
            candidate = script_dir / candidate
        if not candidate.exists():
            raise FileNotFoundError(f"dataset not found: {requested}")
        return candidate.resolve()
    for name in ("BTC_2019_2023_1d.csv", "btc_18_22_1d.csv"):
        for candidate in (Path.cwd() / name, script_dir / name):
            if candidate.exists():
                return candidate.resolve()
    raise FileNotFoundError(
        "no dataset found; provide --data or add BTC_2019_2023_1d.csv"
    )


def select_evaluation_period(data: pd.DataFrame) -> tuple[int, int, bool, str]:
    first_date = data["datetime"].iloc[0].date()
    last_date = data["datetime"].iloc[-1].date()
    last_year = int(data["datetime"].dt.year.max())
    official_coverage = first_date <= date(2019, 1, 1) and last_date >= date(
        2023, 12, 31
    )
    evaluation_year = 2023 if official_coverage else last_year
    label = (
        "2023 untouched out-of-sample"
        if official_coverage
        else f"{evaluation_year} provisional out-of-sample"
    )
    return evaluation_year, evaluation_year, not official_coverage, label


def run_integrity_checks(
    raw_data: pd.DataFrame,
    evaluation_signals: pd.DataFrame,
    config: StrategyConfig,
) -> tuple[dict[str, bool], dict[str, Any], pd.DataFrame, pd.DataFrame]:
    """Assert prefix invariance, shifted indicators, timing, and reproducibility."""
    full_indicators = process_data(raw_data, config)
    full_signals = strat(full_indicators, config)
    cutoffs = sorted(
        {
            min(len(raw_data) - 1, max(config.ema_period + 20, value))
            for value in (300, 700, 1200)
            if len(raw_data) > 1
        }
    )
    for cutoff in cutoffs:
        prefix = raw_data.iloc[: cutoff + 1].copy()
        prefix_indicators = process_data(prefix, config)
        prefix_signals = strat(prefix_indicators, config)
        pd.testing.assert_series_equal(
            prefix_signals["signals"],
            full_signals.loc[:cutoff, "signals"],
            check_names=False,
        )
        for column in (
            "atr",
            "ema_regime",
            "adx",
            "donchian_high",
            "donchian_low",
        ):
            pd.testing.assert_series_equal(
                prefix_indicators[column],
                full_indicators.loc[:cutoff, column],
                check_names=False,
            )

    timing_fixture = pd.DataFrame(
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
    _, timing_trades, _ = run_backtest(timing_fixture)
    assert len(timing_trades) == 1
    assert pd.Timestamp(timing_trades.iloc[0]["entry_time"]) == pd.Timestamp(
        timing_fixture.iloc[1]["datetime"]
    )
    assert float(timing_trades.iloc[0]["entry_price"]) == 110.0
    assert bool(timing_trades.iloc[0]["forced_exit"])

    first = run_backtest(evaluation_signals)
    second = run_backtest(evaluation_signals)
    first_metrics, first_trades, first_equity = first
    second_metrics, second_trades, second_equity = second
    assert json.dumps(first_metrics, sort_keys=True, allow_nan=False) == json.dumps(
        second_metrics, sort_keys=True, allow_nan=False
    )
    pd.testing.assert_frame_equal(first_trades, second_trades)
    pd.testing.assert_frame_equal(first_equity, second_equity)

    checks = {
        "prefix_invariance": True,
        "indicator_invariance": True,
        "next_bar_execution": True,
        "reproducibility": True,
    }
    return checks, first_metrics, first_trades, first_equity


def write_outputs(
    results_dir: Path,
    metrics: dict[str, Any],
    trades: pd.DataFrame,
    equity: pd.DataFrame,
) -> None:
    results_dir.mkdir(parents=True, exist_ok=True)
    (results_dir / "metrics.json").write_text(
        json.dumps(metrics, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    trades.to_csv(results_dir / "trades.csv", index=False, float_format="%.10f")
    equity.to_csv(
        results_dir / "equity_curve.csv", index=False, float_format="%.10f"
    )

    plt.figure(figsize=(10, 5.5))
    plt.plot(equity["datetime"], equity["equity"], color="#155EEF", linewidth=1.8)
    plt.axhline(INITIAL_CAPITAL, color="#667085", linestyle="--", linewidth=0.8)
    plt.title("SatoshiFlow Mark-to-Market Equity")
    plt.xlabel("Date")
    plt.ylabel("Equity (USD)")
    plt.grid(alpha=0.2)
    plt.tight_layout()
    plt.savefig(results_dir / "equity_curve.png", dpi=160)
    plt.close()

    plt.figure(figsize=(10, 4.6))
    plt.fill_between(
        equity["datetime"],
        100.0 * equity["drawdown"],
        0,
        color="#D92D20",
        alpha=0.65,
    )
    plt.title("SatoshiFlow Drawdown")
    plt.xlabel("Date")
    plt.ylabel("Drawdown (%)")
    plt.grid(alpha=0.2)
    plt.tight_layout()
    plt.savefig(results_dir / "drawdown.png", dpi=160)
    plt.close()

    summary = [
        "SATOSHIFLOW VERIFIED BACKTEST",
        f"Dataset: {metrics['dataset_filename']}",
        f"SHA-256: {metrics['dataset_sha256']}",
        f"Dataset range: {metrics['dataset_first_date']} to {metrics['dataset_last_date']}",
        f"Evaluation: {metrics['evaluation_label']}",
        f"Initial capital: ${metrics['initial_capital']:.2f}",
        f"Brokerage rate per transaction: {100 * metrics['brokerage_rate']:.4f}%",
        f"Final equity: ${metrics['final_equity']:.2f}",
        f"Net profit: ${metrics['net_profit']:.2f}",
        f"Net return: {100 * metrics['net_return']:.4f}%",
        f"Sharpe ratio: {metrics['sharpe_ratio']:.6f}",
        f"Maximum drawdown: {100 * metrics['max_drawdown']:.4f}%",
        f"Win rate: {metrics['win_rate']:.4f}%",
        f"Total trades: {metrics['total_trades']}",
        f"Entries / exits / reversals: {metrics['entries']} / {metrics['exits']} / {metrics['reversals']}",
        f"Total brokerage: ${metrics['total_brokerage']:.4f}",
        f"Gross profit before brokerage: ${metrics['gross_profit']:.4f}",
        "LOOKAHEAD CHECK: PASS",
        "REPRODUCIBILITY CHECK: PASS",
    ]
    (results_dir / "backtest_summary.txt").write_text(
        "\n".join(summary) + "\n", encoding="utf-8"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data",
        help="OHLCV CSV path; defaults to BTC_2019_2023_1d.csv, then fallback data",
    )
    parser.add_argument(
        "--results-dir",
        help="output directory (default: Basic Project/results)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    dataset_path = resolve_dataset(args.data)
    results_dir = (
        Path(args.results_dir).resolve()
        if args.results_dir
        else Path(__file__).resolve().parent / "results"
    )
    data = load_dataset(dataset_path)
    digest = dataset_hash(dataset_path)
    eval_start_year, eval_end_year, provisional, evaluation_label = (
        select_evaluation_period(data)
    )

    print(f"Selected dataset: {dataset_path.name}")
    print(f"Rows: {len(data)}")
    print(f"First date: {data['datetime'].iloc[0].isoformat()}")
    print(f"Last date: {data['datetime'].iloc[-1].isoformat()}")
    print(f"SHA-256: {digest}")
    if provisional:
        warnings.warn(
            "Official 2019-2023 dataset is missing. Results are provisional and "
            f"use {eval_start_year} as the final out-of-sample period.",
            stacklevel=1,
        )

    indicators = process_data(data, DEFAULT_CONFIG)
    evaluation_start_index = int(
        data.index[data["datetime"].dt.year >= eval_start_year][0]
    )
    all_signals = strat(
        indicators, DEFAULT_CONFIG, start_index=evaluation_start_index
    )
    evaluation = all_signals[
        all_signals["datetime"].dt.year.between(eval_start_year, eval_end_year)
    ].reset_index(drop=True)
    if evaluation.empty:
        raise RuntimeError("selected evaluation period contains no rows")

    checks, metrics, trades, equity = run_integrity_checks(
        data, evaluation, DEFAULT_CONFIG
    )
    print("LOOKAHEAD CHECK: PASS")
    print("NEXT-BAR EXECUTION CHECK: PASS")
    print("REPRODUCIBILITY CHECK: PASS")

    metrics.update(
        {
            "dataset_filename": dataset_path.name,
            "dataset_sha256": digest,
            "dataset_row_count": int(len(data)),
            "dataset_first_date": data["datetime"].iloc[0].isoformat(),
            "dataset_last_date": data["datetime"].iloc[-1].isoformat(),
            "evaluation_first_date": evaluation["datetime"].iloc[0].isoformat(),
            "evaluation_last_date": evaluation["datetime"].iloc[-1].isoformat(),
            "evaluation_label": evaluation_label,
            "provisional": provisional,
            "parameters": asdict(DEFAULT_CONFIG),
            "lookahead_check": checks["prefix_invariance"]
            and checks["indicator_invariance"],
            "next_bar_execution_check": checks["next_bar_execution"],
            "reproducibility_check": checks["reproducibility"],
        }
    )
    write_outputs(results_dir, metrics, trades, equity)

    print(f"Entries: {metrics['entries']}")
    print(f"Exits: {metrics['exits']}")
    print(f"Reversals: {metrics['reversals']}")
    print(f"Total brokerage paid: ${metrics['total_brokerage']:.4f}")
    print(f"Gross profit before brokerage: ${metrics['gross_profit']:.4f}")
    print(f"Net profit: ${metrics['net_profit']:.4f}")
    print(f"Results: {results_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
