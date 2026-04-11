import pandas as pd
import numpy as np
from strategies.base import VectorStrategy

def calculate_adx(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """Calculates ADX, +DI, and -DI using Wilder's Smoothing."""
    df = df.copy()
    up_move: pd.Series = df['high'] - df['high'].shift(1)
    down_move: pd.Series = df['low'].shift(1) - df['low']
    df['+dm'] = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    df['-dm'] = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    tr1: pd.Series = df['high'] - df['low']
    tr2: pd.Series = (df['high'] - df['close'].shift(1)).abs()
    tr3: pd.Series = (df['low'] - df['close'].shift(1)).abs()
    df['tr'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    wilders_alpha: float = 1 / period
    df['smooth_tr'] = df['tr'].ewm(alpha=wilders_alpha, adjust=False).mean()
    df['smooth_+dm'] = df['+dm'].ewm(alpha=wilders_alpha, adjust=False).mean()
    df['smooth_-dm'] = df['-dm'].ewm(alpha=wilders_alpha, adjust=False).mean()
    df['+di'] = 100 * (df['smooth_+dm'] / df['smooth_tr'])
    df['-di'] = 100 * (df['smooth_-dm'] / df['smooth_tr'])
    dx: pd.Series = 100 * (df['+di'] - df['-di']).abs() / (df['+di'] + df['-di'])
    df['adx'] = dx.ewm(alpha=wilders_alpha, adjust=False).mean()
    return df

class MACDStrategy(VectorStrategy):
    """
    Trend Following with Safety Filter.
    Only trades if ADX > threshold (avoids chop).
    Uses a Smart 2 Exit if the trend dies but it's too choppy to reverse.
    """
    def __init__(
        self,
        fast: int = 12,
        slow: int = 26,
        signal: int = 9,
        adx_threshold: float = 25.0,
        use_vwap: bool = False,
        use_htf: bool = False
    ) -> None:
        self.fast: int = fast
        self.slow: int = slow
        self.signal_span: int = signal
        self.adx_threshold: float = adx_threshold
        self.use_vwap: bool = use_vwap
        self.use_htf: bool = use_htf

    def get_signal_column(self, df: pd.DataFrame) -> pd.Series:
        df = df.copy()
        
        # Calculate moving averages and MACD
        exp1: pd.Series = df['close'].ewm(span=self.fast, adjust=False).mean()
        exp2: pd.Series = df['close'].ewm(span=self.slow, adjust=False).mean()
        macd: pd.Series = exp1 - exp2
        signal_line: pd.Series = macd.ewm(span=self.signal_span, adjust=False).mean()

        df_temp: pd.DataFrame = calculate_adx(df, period=7)
        adx: pd.Series = df_temp['adx']
        is_trending: pd.Series = adx > self.adx_threshold

        # Define entry logic using MACD crossover and ADX trend strength
        buy_cond: pd.Series = (macd > signal_line) & (macd.shift(1) <= signal_line.shift(1)) & is_trending
        sell_cond: pd.Series = (macd < signal_line) & (macd.shift(1) >= signal_line.shift(1)) & is_trending
        
        # Exit conditions when thesis is invalidated (MACD crossover in opposite direction)
        exit_long: pd.Series = (macd < signal_line) & (macd.shift(1) >= signal_line.shift(1))
        exit_short: pd.Series = (macd > signal_line) & (macd.shift(1) <= signal_line.shift(1))

        # Apply optional trend filters (VWAP or HTF)
        if self.use_vwap:
            typical_price: pd.Series = (df['high'] + df['low'] + df['close']) / 3
            vwap: pd.Series = (typical_price * df['volume']).groupby(df.index.date).cumsum() / df['volume'].groupby(df.index.date).cumsum()
            buy_cond = buy_cond & (df['close'] > vwap)
            sell_cond = sell_cond & (df['close'] < vwap)

        if self.use_htf and 'htf_trend' in df.columns:
            buy_cond = buy_cond & (df['htf_trend'] == 1)
            sell_cond = sell_cond & (df['htf_trend'] == -1)

        # Assign final signal series
        signals: pd.Series = pd.Series(0, index=df.index)
        signals.loc[buy_cond] = 1
        signals.loc[sell_cond] = -1
        signals.loc[exit_long & (signals == 0)] = 2
        signals.loc[exit_short & (signals == 0)] = 2

        return signals
