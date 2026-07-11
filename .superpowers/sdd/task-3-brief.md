### Task 3: Implement Full Indicator Set in process_data()

**Files:**
- Modify: `Basic Project/main.py:8-20`

**Interfaces:**
- Consumes: Raw OHLCV dataframe
- Produces: Dataframe with all technical indicators for strategy

**Requirements:**
1. Calculate all necessary indicators for Hypothesis A (regime-filtered trend following)
2. Include trend, volatility, and volume indicators
3. Use pandas_ta for all calculations
4. Handle rolling windows properly (no lookahead bias)

**Specific Indicators to Implement:**
1. **Trend indicators**
   - ADX(14), +DI, -DI (for trend strength)
   - Donchian channels (20-day high/low/mid) OR EMA crossover (fast=12, slow=26)
   
2. **Volatility indicator**
   - ATR(14) (for trailing stops)
   
3. **Volume indicator**
   - Volume z-score (20-day window: (volume - 20-day MA) / 20-day STD)
   
4. **Mean reversion indicators** (for potential future extension)
   - RSI(14)
   
5. **Bollinger Bands** (for squeeze detection)
   - 20-day, 2 STD bands
   - %B position indicator

**Test Command:**
```bash
cd "Basic Project" && python -c "
import pandas as pd
import pandas_ta as ta
exec(open('main.py').read())
data = pd.read_csv('btc_18_22_1d.csv')
data['datetime'] = pd.to_datetime(data['datetime'])
processed = process_data(data)
print('Indicators shape:', processed.shape)
print('Missing values:', processed.isnull().sum().sum())
print('Sample columns:', list(processed.columns)[-10:])
"