"""Crypto futures open interest client.

Fetches aggregate BTC + ETH perpetual futures open interest from Binance
(largest crypto derivatives exchange, ~35% of global OI). No API key needed.
"""

import logging
from typing import Optional

import requests

logger = logging.getLogger(__name__)

BINANCE_FUTURES_URL = "https://fapi.binance.com/fapi/v1"


def _get_oi_usd(symbol: str) -> Optional[float]:
    """Get open interest in USD for a Binance perpetual futures contract.

    Args:
        symbol: e.g. 'BTCUSDT', 'ETHUSDT'

    Returns:
        Open interest in USD, or None on failure
    """
    try:
        oi_resp = requests.get(
            f"{BINANCE_FUTURES_URL}/openInterest",
            params={"symbol": symbol},
            timeout=8,
        )
        oi_resp.raise_for_status()
        oi_data = oi_resp.json()

        price_resp = requests.get(
            f"{BINANCE_FUTURES_URL}/ticker/price",
            params={"symbol": symbol},
            timeout=8,
        )
        price_resp.raise_for_status()
        price_data = price_resp.json()

        oi_qty = float(oi_data["openInterest"])
        price = float(price_data["price"])
        return oi_qty * price
    except Exception as e:
        logger.warning("Failed to fetch %s OI: %s", symbol, e)
        return None


def get_crypto_futures_oi() -> Optional[float]:
    """Get aggregate BTC + ETH perpetual futures OI in billions USD.

    Returns Binance-only OI. Binance represents ~35% of global crypto
    derivatives OI, so multiply by ~2.8 for estimated total market.

    Returns:
        Aggregate OI in billions USD, or None on failure
    """
    try:
        btc_oi = _get_oi_usd("BTCUSDT")
        eth_oi = _get_oi_usd("ETHUSDT")

        if btc_oi is None and eth_oi is None:
            return None

        total = (btc_oi or 0) + (eth_oi or 0)

        # Scale up from Binance-only to estimated total market
        # Binance ≈ 35% of global crypto derivatives OI
        estimated_total = total / 0.35
        return round(estimated_total / 1e9, 2)
    except Exception as e:
        logger.warning("Failed to compute crypto futures OI: %s", e)
        return None
