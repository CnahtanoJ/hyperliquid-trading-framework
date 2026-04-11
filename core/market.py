import time
import pandas as pd
import logging
from typing import Any

logger = logging.getLogger(__name__)

class MarketData:
    def __init__(self, info: Any) -> None:
        self.info: Any = info

    def get_clean_candles(self, coin: str, interval: str = "15m", limit: int = 5000) -> pd.DataFrame:
        try:
            current_time_ms: int = int(time.time() * 1000)
            start_time_ms: int = 0

            raw: Any = self.info.candles_snapshot(coin, interval, start_time_ms, current_time_ms)

            if not raw:
                return pd.DataFrame()

            df: pd.DataFrame = pd.DataFrame(raw).rename(columns={
                't': 'timestamp',
                'o': 'open',
                'h': 'high',
                'l': 'low',
                'c': 'close',
                'v': 'volume'
            })
            df[['open', 'high', 'low', 'close', 'volume']] = df[['open', 'high', 'low', 'close', 'volume']].astype(float)
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            return df.tail(limit).set_index('timestamp')

        except Exception as e:
            logger.error(f"Error fetching candles for {coin}: {e}")
            return pd.DataFrame()
