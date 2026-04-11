import math
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

class AssetManager:
    def __init__(self, info: Optional[Any] = None) -> None:
        self.info: Optional[Any] = info
        self.universe: Dict[str, Any] = {}
        if info:
            try:
                self.universe = {a['name']: a for a in info.meta()['universe']}
            except Exception as e:
                logger.warning(f"AssetManager: Could not fetch universe: {e}")

    def get_price_precision(self, coin: str, price: float) -> float:
        specs: Optional[Dict[str, Any]] = self.universe.get(coin)
        if not specs:
            return float(f"{price:.4g}")
        return float(f"{round(float(price), 6 - specs['szDecimals']):.5g}")

    def round_size(self, coin: str, size: float) -> float:
        specs: Optional[Dict[str, Any]] = self.universe.get(coin)
        if not specs:
            return size
        factor: float = 10 ** specs['szDecimals']
        return math.floor(size * factor) / factor

    def get_safe_tp_size(self, coin: str, total_pos_size: float, tp_pct: float) -> float:
        if not self.info:
            return self.round_size(coin, total_pos_size * tp_pct)

        # 1. Fetch Price
        all_mids: Dict[str, Any] = self.info.all_mids()
        price: float = float(all_mids[coin])

        # 2. Calculate Proposed Size
        target_size: float = total_pos_size * tp_pct
        usd_value: float = target_size * price

        # 3. Define Safety Threshold
        MIN_NOTIONAL: float = 11.0

        if usd_value < MIN_NOTIONAL:
            # logger.info(f"TP Adjustment: Chunk ${usd_value:.2f} too small. Selling ALL.")
            return total_pos_size

        remaining_val: float = (total_pos_size - target_size) * price
        if 0 < remaining_val < MIN_NOTIONAL:
            # logger.info(f"TP Adjustment: Leftover ${remaining_val:.2f} is dust. Selling ALL.")
            return total_pos_size

        return self.round_size(coin, target_size)
