#!/usr/bin/env python3
"""Small, chronological parameter check that never inspects the test year."""

from __future__ import annotations

import argparse
import itertools
import json
from dataclasses import asdict
from pathlib import Path

import numpy as np

from main import (
    StrategyConfig,
    load_dataset,
    process_data,
    resolve_dataset,
    run_backtest,
    strat,
)


def evaluate(data, config: StrategyConfig) -> dict:
    yearly = []
    for year in (2019, 2020, 2021):
        year_indices = data.index[data["datetime"].dt.year == year]
        if year_indices.empty:
            continue
        indicators = process_data(data, config)
        signals = strat(indicators, config, start_index=int(year_indices[0]))
        sample = signals[signals["datetime"].dt.year == year].reset_index(drop=True)
        metrics, _, _ = run_backtest(sample)
        yearly.append(
            {
                "year": year,
                "sharpe_ratio": metrics["sharpe_ratio"],
                "net_return": metrics["net_return"],
                "max_drawdown": metrics["max_drawdown"],
                "total_trades": metrics["total_trades"],
            }
        )
    sharpes = [item["sharpe_ratio"] for item in yearly]
    return {
        "parameters": asdict(config),
        "yearly": yearly,
        "median_sharpe": float(np.median(sharpes)) if sharpes else 0.0,
        "worst_sharpe": float(min(sharpes)) if sharpes else 0.0,
        "total_trades": int(sum(item["total_trades"] for item in yearly)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data")
    parser.add_argument("--output", default="results/validation.json")
    args = parser.parse_args()
    dataset = resolve_dataset(args.data)
    data = load_dataset(dataset)
    if int(data["datetime"].dt.year.max()) < 2021:
        raise RuntimeError("validation requires data through 2021")

    candidates = []
    for donchian, adx, ema, atr_mult in itertools.product(
        (20, 30), (20.0, 25.0), (100, 200), (2.0, 2.5)
    ):
        candidates.append(
            evaluate(
                data,
                StrategyConfig(
                    donchian_period=donchian,
                    adx_threshold=adx,
                    ema_period=ema,
                    atr_stop_multiplier=atr_mult,
                ),
            )
        )
    # Robustness-first: median yearly Sharpe, then worst-year Sharpe, then
    # fewer parameters/trades are not rewarded. The test year is never read.
    ranked = sorted(
        candidates,
        key=lambda item: (
            item["median_sharpe"],
            item["worst_sharpe"],
            item["total_trades"],
        ),
        reverse=True,
    )
    payload = {
        "selection_period": "2019-01-01 through 2021-12-31",
        "selection_rule": "highest median yearly Sharpe, then highest worst-year Sharpe",
        "test_period_excluded": "2022",
        "selected": ranked[0],
        "candidates": ranked,
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload["selected"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
