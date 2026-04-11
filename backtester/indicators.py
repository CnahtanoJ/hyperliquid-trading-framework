import pandas as pd
import numpy as np
from typing import Any

def get_local_poc(df: pd.DataFrame, num_bins: int = 50, lookback: int = 200) -> float:
    """Calculates the Point of Control for the most recent 'lookback' candles."""
    recent_df: pd.DataFrame = df.tail(lookback).copy()
    if recent_df.empty:
        return 0.0
        
    tp: pd.Series = (recent_df['high'] + recent_df['low'] + recent_df['close']) / 3
    min_px: float = float(recent_df['low'].min())
    max_px: float = float(recent_df['high'].max())
    
    if min_px == max_px:
        return min_px
        
    bins: np.ndarray = np.linspace(min_px, max_px, num_bins)
    price_bins: pd.Series = pd.cut(tp, bins=bins, include_lowest=True)
    volume_profile: pd.Series = recent_df.groupby(price_bins, observed=True)['volume'].sum()
    
    poc_bin: Any = volume_profile.idxmax()
    return float(poc_bin.mid)

def get_cvd_slope(df: pd.DataFrame, lookback: int = 5) -> float:
    """Calculates the Proxy CVD and returns the recent momentum slope."""
    if len(df) < lookback + 1:
        return 0.0
        
    candle_range: pd.Series = df['high'] - df['low']
    candle_range = candle_range.replace(0, 1e-9)
    delta: pd.Series = df['volume'] * ((df['close'] - df['open']) / candle_range)
    
    cvd: pd.Series = delta.cumsum()
    slope: float = float(cvd.iloc[-1] - cvd.iloc[-(lookback + 1)])
    return slope

def inject_htf_trend(df_ltf: pd.DataFrame, df_htf: pd.DataFrame, ema_period: int = 50) -> pd.DataFrame:
    """Safely calculates the 1H trend and injects it into the lower timeframe (LTF)."""
    df_htf = df_htf.copy()
    df_htf['htf_ema'] = df_htf['close'].ewm(span=ema_period, adjust=False).mean()
    df_htf['htf_trend'] = np.where(df_htf['close'] > df_htf['htf_ema'], 1, -1)
    
    # The lookahead shift
    df_htf['htf_trend'] = df_htf['htf_trend'].shift(1)
    
    df_ltf = df_ltf.copy()
    df_ltf['htf_trend'] = df_htf['htf_trend'].reindex(df_ltf.index, method='ffill')
    df_ltf['htf_trend'] = df_ltf['htf_trend'].fillna(0) 
    
    return df_ltf
