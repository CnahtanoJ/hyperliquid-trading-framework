import os
import logging
import json
from typing import Any, Dict
from eth_account import Account
from hyperliquid.info import Info
from hyperliquid.exchange import Exchange
from hyperliquid.utils import constants

from core.s3 import S3Interface
from core.state import StateManager
from core.market import MarketData
from core.messaging import send_telegram_message, send_telegram_receipt
from core.assets import AssetManager
from bot.risk import RiskEngine
from bot.engine import HyperliquidBot
from strategies.macd import MACDStrategy

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# CONFIGURATION
AWS_BUCKET: Optional[str] = os.environ.get("AWS_BUCKET")
CONFIG_FILE: str = "strategy_config.json"
TESTNET_MODE: bool = os.environ.get("TESTNET_MODE", "True").lower() == "true"
BASE_URL: str = constants.TESTNET_API_URL if TESTNET_MODE else constants.MAINNET_API_URL

def executor_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    task: str = event.get("task", "execute_trades")
    info: Info = Info(BASE_URL, skip_ws=True)
    
    if TESTNET_MODE:
        KEY: Optional[str] = os.environ.get("TESTNET_PRIVATE_KEY")
        ADDR: Optional[str] = os.environ.get("TESTNET_ACCOUNT_ADDRESS")
    else:
        KEY = os.environ.get("MAINNET_PRIVATE_KEY")
        ADDR = os.environ.get("MAINNET_ACCOUNT_ADDRESS")

    if not KEY or not ADDR or not AWS_BUCKET:
        logger.error("Missing configuration keys or bucket name.")
        return {'statusCode': 500, 'body': 'Configuration Error'}

    if task == "send_daily_report":
        # logic from your original script...
        return {'statusCode': 200, 'body': 'Daily report sent'}

    if task == "execute_trades":
        s3: S3Interface = S3Interface(AWS_BUCKET)
        config: Dict[str, Any] = s3.load_json(CONFIG_FILE)
        
        target_coin: str = config.get("target_coin", "BTC")
        target_tf: str = config.get("timeframe", "15m")
        
        # In the skeleton, we default to MACDStrategy
        strategy: MACDStrategy = MACDStrategy(**config.get("params", {}))
        
        user_state: Dict[str, Any] = info.user_state(ADDR)
        all_mids: Dict[str, Any] = info.all_mids()
        
        account: Account = Account.from_key(KEY)
        exchange: Exchange = Exchange(account, BASE_URL, account_address=ADDR)
        
        risk: RiskEngine = RiskEngine(exchange, info, ADDR, AWS_BUCKET)
        portfolio: Dict[str, Any] = risk.parse_portfolio(user_state, all_mids)
        
        bot: HyperliquidBot = HyperliquidBot(exchange, info, target_coin, target_tf, AWS_BUCKET, strategy, risk)
        bot.run_tick(portfolio, user_state)
        
        return {'statusCode': 200, 'body': 'Executed'}
