#!/usr/bin/env python3
"""
Lookahead Bias Checker.
Tests that signals produced at bar i depend only on data from bars 0..i.
Method: Run strategy on data[0..N], then run on data[0..N+k] and verify
that signals for bars 0..N are identical. If any signal changes, future
data is leaking into past signal computation.
"""
import pandas as pd
import numpy as np
from main import process_data, strat

CSV_PATH = "btc_18_22_1d.csv"
ADX_THRESHOLD = 20

data_full = pd.read_csv(CSV_PATH)
data_full['datetime'] = pd.to_datetime(data_full['datetime'])

total_rows = len(data_full)
print(f"Total rows in dataset: {total_rows}")

# Use a meaningful subset: first 500 rows vs first 700 rows
subset_sizes = [300, 500, 700, total_rows]

prev_signals = None
prev_len = 0
all_pass = True

for size in subset_sizes:
    chunk = data_full.iloc[:size].copy().reset_index(drop=True)
    processed = process_data(chunk)
    result = strat(processed, adx_threshold=ADX_THRESHOLD)
    signals = result['signals'].values.copy()

    if prev_signals is not None:
        # Compare signals for bars 0..prev_len-1
        overlap = min(prev_len, len(signals))
        current_overlap = signals[:overlap]
        prev_overlap = prev_signals[:overlap]

        mismatches = np.where(current_overlap != prev_overlap)[0]
        if len(mismatches) > 0:
            print(f"FAIL: Extending data from {prev_len} to {size} rows changed {len(mismatches)} signal(s) in the overlapping region.")
            for idx in mismatches[:10]:
                print(f"  Bar {idx}: was {prev_overlap[idx]}, now {current_overlap[idx]}")
            all_pass = False
        else:
            print(f"PASS: Signals for bars 0..{overlap-1} are identical between {prev_len}-row and {size}-row runs.")

    prev_signals = signals
    prev_len = len(signals)

print()
if all_pass:
    print("LOOKAHEAD BIAS CHECK: PASS")
    print("No future data leakage detected. Signals at bar i are invariant to data appended after bar i.")
else:
    print("LOOKAHEAD BIAS CHECK: FAIL")
    print("Signals changed when future data was appended. This indicates lookahead bias.")
