import os
import logging
import json
import itertools
from typing import Any, Dict, List, Optional
from hyperliquid.info import Info
from hyperliquid.utils import constants

from core.s3 import S3Interface
from backtester.engine import HyperBacktester
from backtester.indicators import inject_htf_trend
from strategies.macd import MACDStrategy

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

AWS_BUCKET: Optional[str] = os.environ.get("AWS_BUCKET")
CONFIG_FILE: str = "strategy_config.json"
TESTNET_MODE: bool = os.environ.get("TESTNET_MODE", "True").lower() == "true"
BASE_URL: str = constants.TESTNET_API_URL if TESTNET_MODE else constants.MAINNET_API_URL

# For the skeleton, we define a generic strategy config
STRATEGY_CONFIG: Dict[str, Dict[str, Any]] = {
    "MACDStrategy": {
        "class": MACDStrategy,
        "params": {
            "fast": [8, 12], 
            "slow": [21, 26], 
            "adx_threshold": [25]
        }
    }
}

def strategist_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    info_client: Info = Info(BASE_URL, skip_ws=True)
    TICKERS: List[str] = ["HYPE", "SOL", "BTC"]
    TIMEFRAMES: List[str] = ["15m", "1h"]
    
    results: List[Dict[str, Any]] = []
    
    for ticker in TICKERS:
        for tf in TIMEFRAMES:
            try:
                engine: HyperBacktester = HyperBacktester(info_client, ticker, interval=tf)
                if engine.data.empty: continue
                
                # HTF Injection logic if needed...
                
                for strat_name, cfg in STRATEGY_CONFIG.items():
                    keys = list(cfg['params'].keys())
                    values = list(cfg['params'].values())
                    for v in itertools.product(*values):
                        params: Dict[str, Any] = dict(zip(keys, v))
                        strat_instance: Any = cfg['class'](**params)
                        res: Dict[str, Any] = engine.run(strat_instance)
                        
                        results.append({
                            "target_coin": ticker,
                            "timeframe": tf,
                            "strategy": strat_name,
                            "params": params,
                            **res
                        })
            except Exception as e:
                logger.error(f"Error testing {ticker} {tf}: {e}")

    if not results: return {'statusCode': 200, 'body': 'No results'}
    
    # Sort and save the best to S3
    best: Dict[str, Any] = sorted(results, key=lambda x: x.get('profit_factor', 0.0), reverse=True)[0]
    
    if not AWS_BUCKET:
        logger.error("Missing AWS_BUCKET environment variable.")
        return {'statusCode': 500, 'body': 'Configuration Error'}

    s3: S3Interface = S3Interface(AWS_BUCKET)
    s3.save_json(CONFIG_FILE, best)
    
    return {'statusCode': 200, 'body': f"Updated config with {best['target_coin']}"}
