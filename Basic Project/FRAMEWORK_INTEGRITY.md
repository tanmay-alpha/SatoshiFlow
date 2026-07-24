# Organizer framework integrity

## Recovered source

The initial repository commit is `ffd7487758488e56664ba1cb8bb859066d126fd5`.
Its `Basic Project/backtester.py` Git blob is:

`3b94f9749fb64e4fe271fae28d16628ea9fe2519`

The working file has been restored from that exact blob. This can be verified:

```powershell
git rev-parse ffd7487:"Basic Project/backtester.py"
git hash-object "Basic Project/backtester.py"
```

Both commands must print the same blob ID.

## Why verified results do not use its metrics

The organizer PDF requires a signal formed on candle `i` to execute at candle
`i+1` open and defines 0.15% brokerage on entry and exit. The recovered starter
framework:

1. executes a signal using the signal row's `close`;
2. deducts one fee inside `TradePair.pnl()`, not separate entry and exit fees;
3. leaves a final open position incomplete;
4. uses a fixed $1,000 capital base in `calc_capital()`;
5. cannot produce a complete daily mark-to-market equity series under those
   constraints.

Changing these behaviors inside `backtester.py` would violate the explicit
“DO NOT MODIFY” challenge instruction. Therefore `main.py` contains a separate,
documented simulator for local verification and report generation while still
exposing the required `process_data()` and `strat()` functions.

No framework formula was changed to improve performance.
