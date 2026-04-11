import pandas as pd
import numpy as np
from typing import Any, Dict
from core.market import MarketData

class HyperBacktester:
    def __init__(self, info_client: Any, symbol: str, interval: str = "1h", candles_lookback: int = 5000) -> None:
        self.symbol: str = symbol
        self.interval: str = interval
        md: MarketData = MarketData(info_client)
        self.data: pd.DataFrame = md.get_clean_candles(symbol, interval, limit=candles_lookback)
        
        if not self.data.empty:
            self.data['pct_change'] = self.data['close'].pct_change()

    def run(self, strategy_instance: Any, fee_rate: float = 0.001) -> Dict[str, Any]:
        if self.data.empty:
            return {"return": -99.0, "buy_hold": 0.0, "trades": 0}
        
        df: pd.DataFrame = self.data.copy()
        
        try:            
            # 1. Get raw signals
            df['signal'] = strategy_instance.get_signal_column(df)
            
            # 2. ATR Simulation
            atr_tp_mult: float = 1.5 
            atr_sl_mult: float = 2.0
            
            high, low, prev_close = df['high'], df['low'], df['close'].shift(1)
            tr: pd.Series = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
            df['atr'] = tr.rolling(14).mean()

            # 3. Target Calculation
            df['long_tp'] = np.where(df['signal'] == 1, df['close'] + (df['atr'] * atr_tp_mult), np.nan)
            df['long_sl'] = np.where(df['signal'] == 1, df['close'] - (df['atr'] * atr_sl_mult), np.nan)
            
            df['short_tp'] = np.where(df['signal'] == -1, df['close'] - (df['atr'] * atr_tp_mult), np.nan)
            df['short_sl'] = np.where(df['signal'] == -1, df['close'] + (df['atr'] * atr_sl_mult), np.nan)

            trade_blocks: pd.Series = df['signal'].replace(0, np.nan).ffill()
            
            df['long_tp'] = df['long_tp'].groupby(trade_blocks).ffill()
            df['long_sl'] = df['long_sl'].groupby(trade_blocks).ffill()
            df['short_tp'] = df['short_tp'].groupby(trade_blocks).ffill()
            df['short_sl'] = df['short_sl'].groupby(trade_blocks).ffill()

            hit_long_exit: pd.Series = (df['high'] >= df['long_tp']) | (df['low'] <= df['long_sl'])
            hit_short_exit: pd.Series = (df['low'] <= df['short_tp']) | (df['high'] >= df['short_sl'])

            df.loc[(hit_long_exit | hit_short_exit) & (df['signal'] == 0), 'signal'] = 2

            # 4. Positions
            pos_mapper: pd.Series = df['signal'].replace(0, np.nan).replace(2, 0)
            df['position'] = pos_mapper.ffill().fillna(0)
            df.loc[df.index[-1], 'position'] = 0
            
            # 5. Returns
            df['strategy_return'] = (df['position'].shift(1) * df['pct_change']).fillna(0)
            position_change: pd.Series = df['position'].diff().fillna(0)
            position_change.iloc[0] = df['position'].iloc[0] 
            
            df['fees'] = position_change.abs() * fee_rate
            df['net_return'] = df['strategy_return'] - df['fees']

            total_ret: float = float((1 + df['net_return']).cumprod().iloc[-1] - 1)
            hold_ret: float = float((1 + df['pct_change'].fillna(0)).cumprod().iloc[-1] - 1)

            # 24h recent bias
            candles_24h: int = 288 if self.interval == '5m' else (96 if self.interval == '15m' else 24)
            recent_ret: float
            if len(df) > candles_24h:
                recent_ret = float((1 + df['net_return'].iloc[-candles_24h:]).cumprod().iloc[-1] - 1)
            else:
                recent_ret = total_ret

            trades: float = position_change.abs().sum() / 2 

            annual_map: Dict[str, int] = {"5m": 105120, "15m": 35040, "1h": 8760, "4h": 2190, "1d": 365}
            annual_factor: int = annual_map.get(self.interval, 35040)
            sharpe: float = float((df['net_return'].mean() / (df['net_return'].std() + 1e-9)) * np.sqrt(annual_factor))

            gross_profit: float = float(df.loc[df['net_return'] > 0, 'net_return'].sum())
            gross_loss: float = float(df.loc[df['net_return'] < 0, 'net_return'].abs().sum())
            
            profit_factor: float = 99.0 if gross_loss == 0 else float(gross_profit / gross_loss)

            return {
                "return": total_ret, 
                "recent_return": recent_ret,
                "buy_hold": hold_ret, 
                "trades": int(trades),
                "profit_factor": round(profit_factor, 2),
                'sharpe': sharpe
            }
            
        except Exception as e:
            # print(f"Backtest Error: {e}") 
            return {"return": -99.0, "buy_hold": 0.0, "trades": 0}
