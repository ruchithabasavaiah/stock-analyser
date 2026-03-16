import os
import json
import argparse
import requests
from datetime import datetime
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
client = Anthropic()

STRATEGIES = {
    "zero_shot": lambda ticker, prices: f"""Analyze this stock data for {ticker} and give a BUY, HOLD, or SELL signal.

{prices}

Format exactly as:
TREND: [summary]
OBSERVATIONS: [observations]
SIGNAL: [BUY/HOLD/SELL] — [one sentence reasoning]""",

    "few_shot": lambda ticker, prices: f"""Here is an example of good stock analysis:

TREND: NVDA shows a strong upward trend, gaining 8% over 5 days with consistent higher highs.
OBSERVATIONS: Volume increased on up days and decreased on down days, indicating strong buying interest.
SIGNAL: BUY — Bullish volume pattern and momentum suggest continued upside.

Now analyze {ticker} using the same format:

{prices}

Format exactly as:
TREND: [summary]
OBSERVATIONS: [observations]
SIGNAL: [BUY/HOLD/SELL] — [one sentence reasoning]""",

    "chain_of_thought": lambda ticker, prices: f"""Analyze {ticker} step by step.

{prices}

Step 1: Identify the overall price direction
Step 2: Analyze volume patterns and what they indicate
Step 3: Look for any significant price gaps or anomalies
Step 4: Based on steps 1-3, determine the signal

Format your final answer exactly as:
TREND: [summary]
OBSERVATIONS: [observations]
SIGNAL: [BUY/HOLD/SELL] — [one sentence reasoning]"""
}


def get_stock_data(ticker):
    url = f"https://data.alpaca.markets/v2/stocks/{ticker}/bars"
    headers = {
        "APCA-API-KEY-ID": ALPACA_API_KEY,
        "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY
    }
    params = {
        "timeframe": "1Day",
        "start": "2026-03-01",
        "end": "2026-03-14",
        "limit": 5
    }
    response = requests.get(url, headers=headers, params=params)
    return response.json()


def analyze_stock(ticker, price_data, strategy_name):
    bars = price_data.get("bars", [])
    if not bars:
        return None, 0

    prices = "\n".join([
        f"Date: {b['t'][:10]}, Open: ${b['o']:.2f}, Close: ${b['c']:.2f}, Volume: {b['v']}"
        for b in bars
    ])

    prompt = STRATEGIES[strategy_name](ticker, prices)

    start_time = datetime.now()
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}]
    )
    latency_ms = (datetime.now() - start_time).total_seconds() * 1000

    return message.content[0].text, round(latency_ms)


def check_format(analysis):
    required = ["TREND:", "OBSERVATIONS:", "SIGNAL:"]
    return all(field in analysis for field in required)


def log_results(results):
    log_file = "results.json"
    existing = []
    if os.path.exists(log_file):
        with open(log_file, "r") as f:
            existing = json.load(f)
    existing.append(results)
    with open(log_file, "w") as f:
        json.dump(existing, f, indent=2)


def main():
    parser = argparse.ArgumentParser(description="AI Stock Analyzer")
    parser.add_argument(
        "--ticker", nargs="+", default=["AAPL", "GOOGL", "MSFT"],
        help="Ticker symbols to analyze e.g. --ticker NVDA TSLA"
    )
    parser.add_argument(
        "--strategy",
        choices=["zero_shot", "few_shot", "chain_of_thought", "all"],
        default="all",
        help="Prompting strategy to use"
    )
    args = parser.parse_args()

    strategies_to_run = list(STRATEGIES.keys()) if args.strategy == "all" else [args.strategy]
    all_results = []

    print("\nStock Analysis Report")
    print("=" * 60)

    for ticker in args.ticker:
        print(f"\nAnalyzing {ticker}...")
        price_data = get_stock_data(ticker)
        ticker_results = {
            "ticker": ticker,
            "timestamp": datetime.now().isoformat(),
            "strategies": []
        }

        for strategy_name in strategies_to_run:
            print(f"  Running {strategy_name}...")
            analysis, latency = analyze_stock(ticker, price_data, strategy_name)
            if not analysis:
                continue

            format_correct = check_format(analysis)
            ticker_results["strategies"].append({
                "strategy": strategy_name,
                "latency_ms": latency,
                "format_correct": format_correct,
                "analysis": analysis
            })

            print(f"\n  [{strategy_name}] ({latency}ms) (format: {'✓' if format_correct else '✗'})")
            print(f"  {analysis}")
            print(f"  {'-' * 50}")

        all_results.append(ticker_results)
        log_results(ticker_results)

    print("\nResults logged to results.json")
    print("Run 'python report.py' to generate the HTML report")


if __name__ == "__main__":
    main()