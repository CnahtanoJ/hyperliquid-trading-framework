import time
import logging
from typing import Any, Dict, Optional, List
from core.state import StateManager
from core.assets import AssetManager
from core.messaging import send_telegram_message

logger = logging.getLogger(__name__)

class RiskEngine:
    def __init__(
        self,
        exchange: Optional[Any] = None,
        info: Optional[Any] = None,
        account_address: Optional[str] = None,
        bucket: Optional[str] = None
    ) -> None:
        self.exchange: Optional[Any] = exchange
        self.info: Optional[Any] = info
        self.address: Optional[str] = account_address
        self.assets: AssetManager = AssetManager(info)
        self.memory: StateManager = StateManager(bucket_name=bucket) if bucket else None  # type: ignore
        self.dca_spacing: float = 0.02
        self.margin_limit: float = 0.44

    def check_safety(self, user_state: Dict[str, Any]) -> bool:
        try:
            used: float = float(user_state['marginSummary']['totalMarginUsed'])
            val: float = float(user_state['marginSummary']['accountValue'])
            if val == 0:
                logger.error("[RISK ENGINE] Account Value is 0. Aborting.")
                return False
            curr_usage: float = used / val
            if curr_usage > self.margin_limit:
                logger.warning(f"[RISK ENGINE] Margin Usage {curr_usage:.2f} exceeds limit {self.margin_limit}.")
                send_telegram_message(f"[RISK ALERT] High Margin Usage: {curr_usage:.2%}.")
                return False
            return True
        except Exception as e:
            logger.error(f"[RISK ENGINE] Safety check failed: {e}")
            return False

    def clean_global_zombies(self, portfolio: Dict[str, Any], open_orders: List[Dict[str, Any]]) -> None:
        if not self.info or not self.exchange:
            logger.error("[RISK ENGINE] Cannot clean untracked orders: Missing info or exchange client.")
            return

        if not open_orders: return
        active_positions = set(portfolio.keys())

        orders_by_coin: Dict[str, List[Dict[str, Any]]] = {}
        for o in open_orders:
            c: str = o['coin']
            if c not in orders_by_coin: orders_by_coin[c] = []
            orders_by_coin[c].append(o)
            
        for coin, orders in orders_by_coin.items():
            if coin in active_positions:
                continue
            
            is_pending_entry: bool = False
            for o in orders:
                if o['orderType'] == 'Limit':
                    is_reduce_only: bool = bool(o.get('reduceOnly', False) or o.get('r', False))
                    if not is_reduce_only:
                        is_pending_entry = True
                        break
            
            if is_pending_entry:
                continue
            
            logger.warning(f"[RISK ENGINE] Untracked order detected for {coin}")
            send_telegram_message(f"[RISK ENGINE] Canceling untracked orders for {coin}.")
            self.cancel_all_orders(coin)
            time.sleep(1)

    def get_live_sensor_data(self, target_coin: str) -> Optional[Dict[str, float]]:
        if not self.info: return None
        try:
            meta, ctxs = self.info.meta_and_asset_ctxs()
            coin_index: int = next(i for i, asset in enumerate(meta['universe']) if asset['name'] == target_coin)
            coin_ctx: Dict[str, Any] = ctxs[coin_index]
            return {
                "funding_rate": float(coin_ctx['funding']), 
                "oi_usd": float(coin_ctx['openInterest']) * float(coin_ctx['oraclePx']),
                "oracle_price": float(coin_ctx['oraclePx'])
            }
        except Exception as e:
            logger.error(f"[RISK ENGINE] Sensor error for {target_coin}: {e}")
            return None

    def check_execution_safety(self, coin: str, is_buy: bool, current_price: float, poc_price: float) -> bool:
        sensor: Optional[Dict[str, float]] = self.get_live_sensor_data(coin)
        if not sensor: return False

        oi_usd: float = sensor['oi_usd']
        funding: float = sensor['funding_rate']
        
        MIN_OI: float = 10_000_000 
        if oi_usd < MIN_OI: return False

        MAX_FUNDING: float = 0.0200  
        if is_buy and funding > MAX_FUNDING: return False
        if not is_buy and funding < -MAX_FUNDING: return False

        if is_buy and current_price > poc_price: return False
        if not is_buy and current_price < poc_price: return False

        return True

    def parse_portfolio(self, user_state: Dict[str, Any], all_mids: Dict[str, Any], dust_threshold: float = 1.0) -> Dict[str, Any]:
        portfolio: Dict[str, Any] = {}
        if not user_state or 'assetPositions' not in user_state:
            return portfolio
        for p in user_state['assetPositions']:
            pos: Dict[str, Any] = p['position']
            coin: str = pos['coin']
            sz: float = float(pos['szi'])
            if sz == 0: continue
            price: float = float(all_mids.get(coin, 0))
            if abs(sz * price) > dust_threshold:
                portfolio[coin] = pos
        return portfolio

    def cancel_all_orders(self, coin: str) -> None:
        orders: List[Dict[str, Any]] = self.info.open_orders(self.address)
        coin_orders: List[Dict[str, Any]] = [o for o in orders if o['coin'] == coin]
        if not coin_orders: return
        for o in coin_orders:
            try:
                self.exchange.cancel(coin, int(o['oid']))
            except Exception as e:
                logger.error(f"[RISK ENGINE] Failed to cancel order {o['oid']}: {e}")

    def sync_unified_orders(self, coin: str, current_atr_pct: float, portfolio: Dict[str, Any]) -> None:
        pos_details: Optional[Dict[str, Any]] = portfolio.get(coin)
        if not pos_details: return

        sz_raw: float = float(pos_details['szi'])
        total_sz: float = abs(sz_raw)
        avg_entry: float = float(pos_details['entryPx'])
        is_buy_pos: bool = sz_raw > 0
        
        try:
            self.cancel_all_orders(coin)
        except Exception as e:
            logger.error(f"[RISK ENGINE] Error canceling previous orders for {coin}: {e}")
            
        time.sleep(5)
        
        tp_levels: List[Tuple[float, float]] = [(1.0, 1.5)] 
        d: int = 1 if is_buy_pos else -1
        
        for (pct, atr_mult) in tp_levels:
            move: float = current_atr_pct * atr_mult
            tp_px: float = self.assets.get_price_precision(coin, avg_entry * (1 + (move * d)))
            tp_sz: float = self.assets.round_size(coin, total_sz * pct)
            if tp_sz <= 0: continue
            self.exchange.order(
                coin, not is_buy_pos, tp_sz, tp_px, 
                {"trigger": {"isMarket": True, "triggerPx": tp_px, "tpsl": "tp"}},
                reduce_only=True
            )

        sl_mult: float = 2.0
        sl_px: float = self.assets.get_price_precision(coin, avg_entry * (1 - (current_atr_pct * sl_mult * d)))
        self.exchange.order(
            coin, not is_buy_pos, total_sz, sl_px, 
            {"trigger": {"isMarket": True, "triggerPx": sl_px, "tpsl": "sl"}},
            reduce_only=True
        )

    # Simplified sync_break_even for the skeleton
    def sync_break_even(self, coin: str, current_atr_pct: float, portfolio: Dict[str, Any], open_orders: List[Dict[str, Any]]) -> None:
        if coin not in portfolio:
            return
        # Logic for moving SL to breakeven...
        pass
