import requests
import os
import logging

logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

def send_telegram_message(text):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        # logger.info(f"Telegram not configured. Message: {text}")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=15)
    except Exception as e:
        logger.error(f"Telegram error: {e}")

def send_telegram_receipt(stats):
    header_text = "[PROFIT]" if stats['net_profit'] > 0 else "[LOSS]"

    msg = f"**Vault Daily Close {header_text}**\n\n"
    msg += f"Net Profit: `${stats['net_profit']:.2f}`\n"
    msg += f"Gross PnL: `${stats['gross_pnl']:.2f}`\n"
    msg += f"Exchange Fees: `-${stats['fees']:.2f}`\n"
    msg += f"Funding Paid/Earned: `${stats['funding']:.2f}`\n\n"
    msg += f"Trades Executed: `{stats['trades']}`\n"
    msg += f"Volume Traded: `${stats['volume']:,.2f}`\n"

    return msg
