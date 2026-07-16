import pandas as pd
import numpy as np
from backtester import BackTester
import matplotlib.pyplot as plt

# Fixed ADX threshold - selected via walk-forward
ADX_THRESHOLD = 20


def calculate_atr(df, period=14):
    """Calculate the Average True Range (ATR) using Wilder's smoothing."""
    high = df['high']
    low = df['low']
    close = df['close']

    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()

    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1.0 / period, adjust=False).mean()
    atr.iloc[:period - 1] = np.nan
    return atr


def calculate_adx(df, period=14):
    """Calculate the Average Directional Index (ADX)."""
    high = df['high']
    low = df['low']
    close = df['close']

    up_move = high - high.shift(1)
    down_move = low.shift(1) - low

    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)

    plus_dm_smooth = pd.Series(plus_dm).ewm(alpha=1.0/period, adjust=False).mean()
    minus_dm_smooth = pd.Series(minus_dm).ewm(alpha=1.0/period, adjust=False).mean()

    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    tr_smooth = tr.ewm(alpha=1.0/period, adjust=False).mean()

    plus_di = 100 * (plus_dm_smooth / tr_smooth)
    minus_di = 100 * (minus_dm_smooth / tr_smooth)

    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
    adx = dx.ewm(alpha=1.0/period, adjust=False).mean()

    return adx, plus_di, minus_di


def calculate_ema(df, period=14):
    return df['close'].ewm(span=period, adjust=False).mean()


def calculate_rsi(df, period=14):
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calculate_bollinger_bands(df, period=20, std_dev=2):
    sma = df['close'].rolling(window=period).mean()
    std = df['close'].rolling(window=period).std()
    upper_band = sma + (std * std_dev)
    lower_band = sma - (std * std_dev)
    return upper_band, sma, lower_band


def process_data(data):
    data['ATR'] = calculate_atr(data, period=14)
    data['ADX'], data['DI+'], data['DI-'] = calculate_adx(data, period=14)
    data['ema_fast'] = calculate_ema(data, period=12)
    data['ema_slow'] = calculate_ema(data, period=26)
    data['donchian_high'] = data['high'].rolling(window=20).max()
    data['donchian_low'] = data['low'].rolling(window=20).min()
    data['donchian_mid'] = (data['donchian_high'] + data['donchian_low']) / 2
    data['volume_ma20'] = data['volume'].rolling(window=20).mean()
    data['volume_std20'] = data['volume'].rolling(window=20).std()
    data['volume_zscore'] = (data['volume'] - data['volume_ma20']) / data['volume_std20']
    data['RSI'] = calculate_rsi(data, period=14)
    data['bb_upper'], data['bb_mid'], data['bb_lower'] = calculate_bollinger_bands(data, period=20, std_dev=2)
    data['bb_percent'] = (data['close'] - data['bb_lower']) / (data['bb_upper'] - data['bb_lower'])
    return data


def strat(data, adx_threshold=None):
    """Volume Spike Trend Follower with ADX Regime Filter."""
    if adx_threshold is None:
        adx_threshold = ADX_THRESHOLD

    data['trade_type'] = "HOLD"
    data['signals'] = 0
    position = 0  # 0 = flat, 1 = long, -1 = short

    atr_multiplier = 2.0
    trailing_stop = 0
    num_wrong = 0

    for i in range(14, len(data)):
        vol_spike = data.loc[i-6:i-1, 'volume'].mean() + 1.5 * data.loc[i-6:i-1, 'volume'].std()
        strong_trend = data.loc[i, 'ADX'] >= adx_threshold

        if position == 0:
            if data.loc[i, 'volume'] > vol_spike and strong_trend:
                if data.loc[i, 'close'] > data.loc[i, 'open']:
                    data.loc[i, 'signals'] = 1
                    position = 1
                    data.loc[i, 'trade_type'] = "LONG"
                    trailing_stop = data.loc[i, 'close'] - (data.loc[i, 'ATR'] * atr_multiplier)
                elif data.loc[i, 'close'] < data.loc[i, 'open']:
                    data.loc[i, 'signals'] = -1
                    position = -1
                    data.loc[i, 'trade_type'] = "SHORT"
                    trailing_stop = data.loc[i, 'close'] + (data.loc[i, 'ATR'] * atr_multiplier)

        elif position == 1:
            trend_rev = data.loc[i, 'volume'] >= vol_spike and data.loc[i, 'close'] < data.loc[i, 'open']

            if data.loc[i, 'close'] <= data.loc[i-1, 'close']:
                num_wrong += 1
            else:
                num_wrong = 0

            if trend_rev:
                data.loc[i, 'signals'] = -2
                position = -1
                trailing_stop = data.loc[i, 'close'] + (data.loc[i, 'ATR'] * atr_multiplier)
                num_wrong = 0
                data.loc[i, 'trade_type'] = "REVERSE_LONG_TO_SHORT"
            elif num_wrong == 3:
                data.loc[i, 'signals'] = -1
                position = 0
                num_wrong = 0
                data.loc[i, 'trade_type'] = "CLOSE"
            else:
                if data.loc[i, 'close'] < trailing_stop:
                    data.loc[i, 'signals'] = -1
                    position = 0
                    data.loc[i, 'trade_type'] = 'CLOSE'
                else:
                    trailing_stop = max(trailing_stop, data.loc[i, 'close'] - (data.loc[i, 'ATR'] * atr_multiplier))

        elif position == -1:
            trend_rev = data.loc[i, 'volume'] >= vol_spike and data.loc[i, 'close'] > data.loc[i, 'open']

            if data.loc[i, 'close'] >= data.loc[i-1, 'close']:
                num_wrong += 1
            else:
                num_wrong = 0

            if trend_rev:
                data.loc[i, 'signals'] = 2
                position = 1
                trailing_stop = data.loc[i, 'close'] - (data.loc[i, 'ATR'] * atr_multiplier)
                num_wrong = 0
                data.loc[i, 'trade_type'] = "REVERSE_SHORT_TO_LONG"
            elif num_wrong == 3:
                data.loc[i, 'signals'] = 1
                position = 0
                num_wrong = 0
                data.loc[i, 'trade_type'] = "CLOSE"
            else:
                if data.loc[i, 'close'] > trailing_stop:
                    data.loc[i, 'signals'] = 1
                    position = 0
                    data.loc[i, 'trade_type'] = 'CLOSE'
                else:
                    trailing_stop = min(trailing_stop, data.loc[i, 'close'] + (data.loc[i, 'ATR'] * atr_multiplier))

    return data


def main():
    data = pd.read_csv("btc_18_22_1d.csv")
    data['datetime'] = pd.to_datetime(data['datetime'])

    # Run on train=[2018-2020], validate=[2021] with ADX_THRESHOLD=20
    val_start = "2021-01-01"
    val_end = "2021-12-31"

    lookback_data = data[data['datetime'] < val_start].tail(90)
    val_window = data[(data['datetime'] >= val_start) & (data['datetime'] <= val_end)]

    combined = pd.concat([lookback_data, val_window], ignore_index=True).reset_index(drop=True)
    processed = process_data(combined)

    val_only_start_idx = len(lookback_data)
    val_data = processed.iloc[val_only_start_idx:].copy().reset_index(drop=True)
    result_data = strat(val_data)

    csv_file_path = "final_data.csv"
    result_data.to_csv(csv_file_path, index=False)

    # Run backtester - NOTE: get_trades() is called with 1000 as argument
    bt = BackTester("BTC", signal_data_path=csv_file_path, master_file_path=csv_file_path, compound_flag=1)
    bt.get_trades(1000)

    stats = bt.get_statistics()
    if stats:
        print(f"Sharpe Ratio: {stats.get('Sharpe Ratio', 0):.4f}")
        print(f"Max Drawdown %: {stats.get('Maximum Drawdown(%)', 0):.2f}")
        print(f"Net Profit: ${stats.get('Net Profit', 0):.2f}")
        print(f"Win Rate %: {stats.get('Win Rate', 0):.2f}")
        print(f"Total Trades: {stats.get('Total Trades', 0)}")
    else:
        print("Stats is None - no trades generated")
        return None

    # ---- Lookahead bias check ----
    # Re-runs process_data + strat on truncated data for each signal bar,
    # verifying that signals at bar i depend only on data from bars 0..i.
    print("\nChecking for lookahead bias...")
    lookahead_bias = False
    signal_bars = [i for i in range(len(result_data)) if result_data.loc[i, 'signals'] != 0]
    print(f"  Verifying {len(signal_bars)} signal bars...")

    raw_lookback = data[data['datetime'] < val_start].tail(90)
    raw_val = data[(data['datetime'] >= val_start) & (data['datetime'] <= val_end)]

    for idx in signal_bars:
        temp_val_trunc = raw_val.iloc[:idx + 1]
        temp_comb = pd.concat([raw_lookback, temp_val_trunc], ignore_index=True).reset_index(drop=True)
        temp_comb = process_data(temp_comb)
        lb_len = len(raw_lookback)
        temp_result = temp_comb.iloc[lb_len:].copy().reset_index(drop=True)
        temp_result = strat(temp_result)
        if temp_result.loc[idx, 'signals'] != result_data.loc[idx, 'signals']:
            print(f"  Lookahead bias at bar {idx}: full-run signal={result_data.loc[idx, 'signals']}, truncated={temp_result.loc[idx, 'signals']}")
            lookahead_bias = True

    if lookahead_bias:
        print("  FAIL: Lookahead bias detected!")
    else:
        print("  PASS: No lookahead bias detected.")

    # Generate equity curve plot
    bt.calc_capital()

    fig, ax1 = plt.subplots(figsize=(14, 7))

    ax1.plot(bt.data.index, bt.data['close'], color='gray', alpha=0.7, label='BTC Close')
    ax1.set_xlabel('Date')
    ax1.set_ylabel('BTC Price (USD)', color='gray')
    ax1.tick_params(axis='y', labelcolor='gray')

    ax2 = ax1.twinx()
    ax2.plot(bt.data.index, bt.data['capital'], color='blue', label='Capital')
    ax2.set_ylabel('Capital (USD)', color='blue')
    ax2.tick_params(axis='y', labelcolor='blue')

    plt.title(f"Equity Curve - BTC Strategy (ADX Threshold={ADX_THRESHOLD})")
    fig.tight_layout()

    plot_path = "equity_curve_2021.png"
    plt.savefig(plot_path, dpi=150)
    plt.close()
    print(f"Plot saved to: {plot_path}")

    return plot_path


if __name__ == "__main__":
    main()
