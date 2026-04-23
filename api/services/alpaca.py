from __future__ import annotations

import os
from datetime import datetime, timedelta

import httpx
from dotenv import load_dotenv

load_dotenv()

ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")


async def get_stock_data(ticker: str) -> dict:
    url = f"https://data.alpaca.markets/v2/stocks/{ticker}/bars"
    headers = {
        "APCA-API-KEY-ID": ALPACA_API_KEY,
        "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
    }
    now = datetime.now()
    params = {
        "timeframe": "1Day",
        "start": (now - timedelta(days=7)).strftime("%Y-%m-%d"),
        "end": now.strftime("%Y-%m-%d"),
        "limit": 5,
        "feed": "iex",
    }
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()


def format_bars(bars: list[dict]) -> str:
    return "\n".join([
        f"Date: {b['t'][:10]}, Open: ${b['o']:.2f}, Close: ${b['c']:.2f}, Volume: {b['v']}"
        for b in bars
    ])
