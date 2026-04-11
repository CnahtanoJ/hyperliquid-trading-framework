# Hyperliquid Trading Framework Skeleton

A modular, production-ready framework for building and backtesting trading strategies on the Hyperliquid DEX, designed for AWS Lambda deployment.

## Overview

This framework separates strategy logic from execution, allowing you to:
1.  **Backtest**: Run historical simulations to find the best coin/timeframe/parameters.
2.  **Trade**: Deploy your best-performing strategy to live market execution on AWS Lambda.
3.  **Manage Risk**: Built-in ATR-based TP/SL, DCA logic, and safety sensors.

## Project Structure

- `backtester/`: Engine for running historical simulations and indicator math.
- `bot/`: The live trading engine and sophisticated `RiskEngine`.
- `core/`: Infrastructure utilities for S3, state management, assets, and messaging.
- `handlers/`: AWS Lambda entry points for the Bot and the Strategist.
- `strategies/`: Where you define your alpha. Includes a real MACD example.

## Setup

1.  **Clone the Repository**:
    ```bash
    git clone https://github.com/your-username/hyperliquid-trading-framework.git
    cd hyperliquid-trading-framework
    ```
2.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```
3.  **Configure Environment**:
    - Copy `.env.example` to `.env`.
    - Fill in your Hyperliquid API keys, AWS credentials, and Telegram tokens.

4.  **Define Your Strategy**:
    - Inherit from `VectorStrategy` in `strategies/base.py`.
    - Implement `get_signal_column`.

## Deployment

This project is built for AWS Lambda:
- **Strategist**: Trigger daily via Amazon EventBridge to find the best strategies.
- **Executor**: Trigger every candle close (e.g., every 15m) to process trades.

## Disclaimer

Trading carries significant risk. This framework is provided "as-is" for educational and structural purposes. Always test on Testnet before going live with real capital.
