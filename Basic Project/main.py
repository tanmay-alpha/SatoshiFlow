import pandas as pd
import numpy as np
from backtester import BackTester


def calculate_atr(df, period=14):
    """
    Calculate the Average True Range (ATR) using Wilder's smoothing.
    """
    high = df['high']
    low = df['low']
    close = df['close']

    # True Range (TR) calculation
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()

    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    # Wilder's Smoothing: EMA with alpha = 1 / period
    atr = tr.ewm(alpha=1.0 / period, adjust=False).mean()

    # Set the first 'period - 1' values to NaN since they don't have enough data
    atr.iloc[:period - 1] = np.nan
    return atr


def process_data(data):
    """
    Process the input data and return a dataframe with all the necessary indicators and data for making signals.

    Parameters:
    data (pandas.DataFrame): The input data to be processed.

    Returns:
    pandas.DataFrame: The processed dataframe with all the necessary indicators and data.
    """
    # Generate the necessary indicators here
    data['ATR'] = calculate_atr(data, period=14)
    return data


def calculate_adx(df, period=14):
    """
    Calculate the Average Directional Index (ADX).
    """
    high = df['high']
    low = df['low']
    close = df['close']

    # Calculate price changes
    up_move = high - high.shift(1)
    down_move = low.shift(1) - low

    # Calculate directional movement
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)

    # Smooth directional movement
    plus_dm_smooth = pd.Series(plus_dm).ewm(alpha=1.0/period, adjust=False).mean()
    minus_dm_smooth = pd.Series(minus_dm).ewm(alpha=1.0/period, adjust=False).mean()

    # Calculate true range
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    tr_smooth = tr.ewm(alpha=1.0/period, adjust=False).mean()

    # Calculate directional indices
    plus_di = 100 * (plus_dm_smooth / tr_smooth)
    minus_di = 100 * (minus_dm_smooth / tr_smooth)

    # Calculate DX and ADX
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
    adx = dx.ewm(alpha=1.0/period, adjust=False).mean()

    return adx, plus_di, minus_di


def calculate_ema(df, period=14):
    """
    Calculate Exponential Moving Average.
    """
    return df['close'].ewm(span=period, adjust=False).mean()


def calculate_rsi(df, period=14):
    """
    Calculate Relative Strength Index (RSI).
    """
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calculate_bollinger_bands(df, period=20, std_dev=2):
    """
    Calculate Bollinger Bands.
    """
    sma = df['close'].rolling(window=period).mean()
    std = df['close'].rolling(window=period).std()
    upper_band = sma + (std * std_dev)
    lower_band = sma - (std * std_dev)
    return upper_band, sma, lower_band


def process_data(data):
    """
    Process the input data and return a dataframe with all necessary indicators.
    """
    # Basic indicators
    data['ATR'] = calculate_atr(data, period=14)

    # Trend indicators
    data['ADX'], data['DI+'], data['DI-'] = calculate_adx(data, period=14)

    # Moving averages for trend following
    data['ema_fast'] = calculate_ema(data, period=12)
    data['ema_slow'] = calculate_ema(data, period=26)

    # Donchian channels for breakout detection
    data['donchian_high'] = data['high'].rolling(window=20).max()
    data['donchian_low'] = data['low'].rolling(window=20).min()
    data['donchian_mid'] = (data['donchian_high'] + data['donchian_low']) / 2

    # Volume indicators
    data['volume_ma20'] = data['volume'].rolling(window=20).mean()
    data['volume_std20'] = data['volume'].rolling(window=20).std()
    data['volume_zscore'] = (data['volume'] - data['volume_ma20']) / data['volume_std20']

    # Mean reversion indicators
    data['RSI'] = calculate_rsi(data, period=14)

    # Bollinger Bands
    data['bb_upper'], data['bb_mid'], data['bb_lower'] = calculate_bollinger_bands(data, period=20, std_dev=2)
    data['bb_percent'] = (data['close'] - data['bb_lower']) / (data['bb_upper'] - data['bb_lower'])

    return data


def strat(data, adx_threshold=25):
    """
    Create a strategy based on indicators or other factors.

    Parameters:
    - data: DataFrame
        The input data containing the necessary columns for strategy creation.

    Returns:
    - DataFrame
        The modified input data with an additional 'signals' column representing the strategy signals.
    """
    data['trade_type'] = "HOLD" 
    data['signals'] = 0
    position = 0 # Variable to keep track of the current position (0 = no position, 1 = long, -1 = short)

    # Example strategy
    num_wrong = 0
    trailing_stop = 0  
    trailing_stop_multiplier=2

    for i in range(14, len(data)): # Starting from the 14th index to ensure ATR can be calculated

        # Check if there is a volume spike
        vol_spike=np.mean(data.loc[i -5: i, 'volume']) + 1.5*np.std(data.loc[i -5: i, 'volume'])

        if position == 0:
            if data.loc[i, 'volume'] > vol_spike:
                if data.loc[i,'close']>data.loc[i,'open']:
                    data.loc[i, 'signals'] = 1 # Buy signal
                    position = 1 # Update the position to keep track of the current position
                    data.loc[i, 'trade_type'] = "LONG"
                    trailing_stop = data.loc[i,'close'] - (data.iloc[i]["ATR"] * trailing_stop_multiplier) # Set the initial trailing stop

                elif data.loc[i,'close']<data.loc[i,'open']:
                    data.loc[i, 'signals'] = -1
                    position = -1
                    data.loc[i, 'trade_type'] = "SHORT"
                    trailing_stop = data.loc[i,'close'] + (data.iloc[i]["ATR"] * trailing_stop_multiplier)

        elif position == 1: # We already have a long position
            # Check if the direction of the trend reversed
            trend_rev=data.loc[i, 'volume'] >= vol_spike and data.loc[i,'close']<data.loc[i,'open']
            
            # Check if the price has gone down for 3 consecutive candles
            if data.loc[i, 'close'] <= data.loc[i - 1, 'close']:
                num_wrong += 1
            else:
                num_wrong = 0

            if trend_rev: # Trend reversal detected
                # Reverse the position
                data.loc[i, 'signals'] = -2
                position = -1
                trailing_stop = data.loc[i,'close'] + (data.iloc[i]["ATR"] * trailing_stop_multiplier)
                num_wrong=0
                data.loc[i, 'trade_type'] = "REVERSE_LONG_TO_SHORT"
            elif num_wrong == 3: # Price has gone down for 3 consecutive candles
                # Close the position
                data.loc[i, 'signals'] = -1
                position = 0
                num_wrong = 0 
                data.loc[i, 'trade_type'] = "CLOSE"
            else : 
                # Check if the trailing stop has been hit
                if data.iloc[i]["close"] < trailing_stop:
                    data.loc[i, 'signals'] = -1
                    position = 0
                    data.loc[i, 'trade_type'] = 'CLOSE'
                else: # Update the trailing stop
                    trailing_stop = max(trailing_stop, data.iloc[i]["close"] - (data.iloc[i]["ATR"] * trailing_stop_multiplier))
            
                
                    
        elif position == -1: # We already have a short position
            # Check if the direction of the trend reversed
            trend_rev=data.loc[i, 'volume'] >= vol_spike and data.loc[i,'close']>data.loc[i,'open']
            
            # Check if the price has gone up for 3 consecutive candles
            if data.loc[i, 'close'] >= data.loc[i - 1, 'close']:
                num_wrong += 1
            else:
                num_wrong = 0

            if trend_rev: # Trend reversal detected
                # Reverse the position
                data.loc[i, 'signals'] = 2
                position = 1
                trailing_stop = data.loc[i,'close'] - (data.iloc[i]["ATR"] * trailing_stop_multiplier)
                num_wrong=0
                data.loc[i, 'trade_type'] = "REVERSE_SHORT_TO_LONG"
            elif num_wrong == 3: # Price has gone up for 3 consecutive candles
                # Close the position
                data.loc[i, 'signals'] = 1
                position = 0
                num_wrong=0
                data.loc[i, 'trade_type'] = "CLOSE"
            else: 
                # Check if the trailing stop has been hit
                if data.iloc[i]["close"] > trailing_stop:
                    data.loc[i, 'signals'] = 1
                    position = 0
                    data.loc[i, 'trade_type'] = 'CLOSE'
                else: # Update the trailing stop
                    trailing_stop = min(trailing_stop, data.iloc[i]["close"] + (data.iloc[i]["ATR"] * trailing_stop_multiplier))
    return data

def main():
    data = pd.read_csv("btc_18_22_1d.csv")
    processed_data = process_data(data) # process the data
    result_data = strat(processed_data) # Apply the strategy
    csv_file_path = "final_data.csv" 
    result_data.to_csv(csv_file_path, index=False)

    bt = BackTester("BTC", signal_data_path="final_data.csv", master_file_path="final_data.csv", compound_flag=1)
    bt.get_trades(1000)

    # print trades and their PnL
    for trade in bt.trades: 
        print(trade)
        print(trade.pnl())

    # Print results
    stats = bt.get_statistics()
    for key, val in stats.items():
        print(key, ":", val)


    #Check for lookahead bias
    print("Checking for lookahead bias...")
    lookahead_bias = False
    for i in range(len(result_data)):
        if result_data.loc[i, 'signals'] != 0:  # If there's a signal
            temp_data = data.iloc[:i+1].copy()  # Take data only up to that point
            temp_data = process_data(temp_data) # process the data
            temp_data = strat(temp_data, adx_threshold=25) # Re-run strategy
            if temp_data.loc[i, 'signals'] != result_data.loc[i, 'signals']:
                print(f"Lookahead bias detected at index {i}")
                lookahead_bias = True

    if not lookahead_bias:
        print("No lookahead bias detected.")

    # Generate the PnL graph
    # bt.make_trade_graph()
    # bt.make_pnl_graph()
    
if __name__ == "__main__":
    main()