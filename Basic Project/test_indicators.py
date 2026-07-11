#!/usr/bin/env python3
import pandas as pd
import sys
sys.path.append('.')
from main import process_data

# Load test data
data = pd.read_csv('btc_18_22_1d.csv')
data['datetime'] = pd.to_datetime(data['datetime'])

# Process data with indicators
processed = process_data(data)

# Print results
print("✓ All indicators calculated successfully!")
print(f"Data shape: {processed.shape}")
print("\nIndicator columns:")
indicator_cols = [col for col in processed.columns if col not in ['datetime', 'open', 'high', 'low', 'close', 'volume', 'nextdatetime']]
for col in indicator_cols:
    non_null_count = processed[col].notna().sum()
    print(f"  {col}: {non_null_count}/{len(processed)} values")