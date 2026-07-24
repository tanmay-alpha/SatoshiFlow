# Organizer framework integrity

## Recovered source

The initial repository commit is `ffd7487758488e56664ba1cb8bb859066d126fd5`.
Its organizer-provided `Basic Project/backtester.py` is Git blob:

`3b94f9749fb64e4fe271fae28d16628ea9fe2519`

The working file is unchanged from that blob:

```powershell
git rev-parse ffd7487:"Basic Project/backtester.py"
git hash-object "Basic Project/backtester.py"
```

Both commands print the same ID.

## Official execution path

`main.py` imports `BackTester` directly:

```python
from backtester import BackTester
```

It writes the generated signals and calls the original public API normally:

```python
bt = BackTester(
    "BTC",
    signal_data_path=final_data_path,
    master_file_path=final_data_path,
    compound_flag=1,
)
bt.get_trades(1000)
stats = bt.get_statistics()
```

Those returned statistics are the official headline results. The organizer
file is not patched or wrapped.

## Timing adaptation

The framework executes a signal at its row's close. The strategy prevents
same-row decision execution by calculating the decision after completed bar
`t`, then placing its valid signal on bar `t+1`. This yields conservative
next-bar-close execution while preserving the official engine.

## Fee behavior

The challenge configuration is 0.15%. In the recovered framework,
`TradePair.pnl()` deducts `0.0015 * abs(qty)` once per completed trade, rather
than separate entry and exit notionals. The official output reports that
behavior exactly. It is not modified to improve or penalize results.

`research_backtest.py` remains a clearly secondary audit with next-open
execution, daily mark-to-market equity, and separate 0.15% entry and exit
fees. Its outputs are isolated under `results/research/` and are never used
as the organizer headline table.
