import pandas as pd
import logging
import time
from typing import Any, Dict, Optional
from core.market import MarketData
from core.messaging import send_telegram_message
from backtester.indicators import get_local_poc, get_cvd_slope
from bot.risk import RiskEngine

logger = logging.getLogger(__name__)

class HyperliquidBot:
    def __init__(
        self,
        exchange: Any,
        info: Any,
        coin: str,
        timeframe: str,
        bucket: str,
        strategy: Any,
        risk_engine: RiskEngine
    ) -> None:
        self.exchange: Any = exchange
        self.info: Any = info
        self.address: str = exchange.account_address 
        self.coin: str = coin
        self.timeframe: str = timeframe
        self.strategy: Any = strategy
        self.md: MarketData = MarketData(self.info)
        self.risk: RiskEngine = risk_engine

    def run_tick(self, portfolio: Dict[str, Any], user_state: Dict[str, Any]) -> None:
        if not self.risk.check_safety(user_state): 
            return
            
        df: pd.DataFrame = self.md.get_clean_candles(self.coin, interval=self.timeframe, limit=1000)
        if df.empty: return

        high, low = df['high'], df['low']
        prev_close = df['close'].shift(1)
        tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
        df['atr_pct'] = (tr.rolling(14).mean() / df['close'])
        
        current_atr_pct: float = float(df['atr_pct'].iloc[-1]) if pd.notna(df['atr_pct'].iloc[-1]) else 0.015

        open_orders: Any = self.info.frontend_open_orders(self.address)
        self.risk.clean_global_zombies(portfolio, open_orders)
        self.risk.sync_break_even(self.coin, current_atr_pct, portfolio, open_orders)

        signals: pd.Series = self.strategy.get_signal_column(df)
        current_signal: int = int(signals.iloc[-2])

        if current_signal == 0:
            return 

        poc_price: float = float(get_local_poc(df, num_bins=50, lookback=200))
        current_price: float = float(df['close'].iloc[-1])
        
        if current_signal == 1: 
            if self.risk.check_execution_safety(self.coin, is_buy=True, current_price=current_price, poc_price=poc_price):
                send_telegram_message(f"[ENTRY LONG] Signal confirmed for {self.coin} at ${current_price:.4f}")
                self.execute_logic(self.coin, "BULLISH", current_atr_pct, portfolio, user_state, open_orders)

        elif current_signal == -1: 
            if self.risk.check_execution_safety(self.coin, is_buy=False, current_price=current_price, poc_price=poc_price):
                send_telegram_message(f"[ENTRY SHORT] Signal confirmed for {self.coin} at ${current_price:.4f}")
                self.execute_logic(self.coin, "BEARISH", current_atr_pct, portfolio, user_state, open_orders)

        elif current_signal == 2:
            if self.coin in portfolio:
                send_telegram_message(f"[EXIT] Closing position for {self.coin}")
                self.execute_logic(self.coin, "EXIT", current_atr_pct, portfolio, user_state, open_orders)

    def execute_logic(
        self,
        coin: str,
        signal: str,
        current_atr_pct: float,
        portfolio: Dict[str, Any],
        user_state: Dict[str, Any],
        open_orders: Any
    ) -> None:
        # Implementation of order execution logic...
        # This will call self.exchange.order(...)
        pass
