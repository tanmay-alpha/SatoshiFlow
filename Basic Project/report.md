# SatoshiFlow organizer-compatible report

## Dataset

- File: `btc_18_22_1d.csv`
- Range: 2018-01-01 to 2022-12-31
- SHA-256: `32814cd9f3b83dc79a0092c1f1c24bd988dad4c4b230dcd421401025ac660748`

The supplied repository dataset covers 2018-2022. The strategy is generic and
is designed to run unchanged on evaluator-provided OHLCV data.

## Official organizer-framework metrics

| Metric | Value |
|---|---:|
| Final capital | $5,463.61 |
| Net return | 446.3613% |
| Sharpe ratio | 1.011695 |
| Maximum drawdown | 21.3665% |
| Win rate | 55.1724% |
| Total trades | 29 |
| Benchmark return | 23.6353% |

Decision on completed candle `t` is shifted to candle `t+1`, where the
unchanged organizer backtester executes it at the close.

## Independent robustness check

The separate next-open mark-to-market engine produced final equity
$3,743.40, Sharpe 0.818167, and
maximum drawdown 54.6380%. These are secondary,
stricter diagnostics, not official headline results.

## Integrity

- LOOKAHEAD CHECK: PASS
- SIGNAL SHIFT CHECK: PASS
- SIGNAL VALIDITY CHECK: PASS
- ORGANIZER BACKTESTER CHECK: PASS
- REPRODUCIBILITY CHECK: PASS

The PDF and this file are generated from `results/organizer/metrics.json` and
the clearly separated `results/research/metrics.json`.
