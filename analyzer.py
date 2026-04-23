from __future__ import annotations

import asyncio
import argparse

from api.db import create_db, save_result
from api.services.alpaca import format_bars, get_stock_data
from api.services.claude import STRATEGIES, check_format, extract_signal, run_analysis
from api.services.evaluator import detect_hallucination
from report import generate_report


async def analyze_ticker_strategy(
    ticker: str, price_data: dict, strategy_name: str
) -> dict | None:
    bars = price_data.get("bars", [])
    if not bars:
        print(f"  [{ticker}] No data available")
        return None

    prices = format_bars(bars)
    analysis, latency_ms, input_tokens, output_tokens = await run_analysis(ticker, prices, strategy_name)
    signal = extract_signal(analysis)
    format_correct = check_format(analysis)
    hall = detect_hallucination(analysis, prices)

    save_result(
        ticker, strategy_name, signal, latency_ms, format_correct, analysis,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        hallucination_detected=hall["hallucination_detected"],
        flagged_terms=",".join(hall["flagged_terms"]),
    )

    return {
        "ticker": ticker,
        "strategy": strategy_name,
        "latency_ms": latency_ms,
        "format_correct": format_correct,
        "signal": signal,
        "analysis": analysis,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "hallucination_detected": hall["hallucination_detected"],
        "flagged_terms": hall["flagged_terms"],
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description="AI Stock Analyzer")
    parser.add_argument(
        "--ticker", nargs="+", default=["AAPL", "GOOGL", "MSFT"],
        help="Ticker symbols to analyze e.g. --ticker NVDA TSLA",
    )
    parser.add_argument(
        "--strategy",
        choices=["zero_shot", "few_shot", "chain_of_thought", "self_critique", "all"],
        default="all",
        help="Prompting strategy to use",
    )
    args = parser.parse_args()

    create_db()

    tickers = [t.upper() for t in args.ticker]
    strategies_to_run = list(STRATEGIES.keys()) if args.strategy == "all" else [args.strategy]

    print("\nFetching stock data...")
    price_data_list = await asyncio.gather(*[get_stock_data(ticker) for ticker in tickers])
    ticker_prices = dict(zip(tickers, price_data_list))

    print("Running analysis...\n")
    tasks = [
        analyze_ticker_strategy(ticker, ticker_prices[ticker], strategy)
        for ticker in tickers
        for strategy in strategies_to_run
    ]
    results = await asyncio.gather(*tasks)

    print("\nStock Analysis Report")
    print("=" * 60)

    for result in results:
        if result:
            fmt = "✓" if result["format_correct"] else "✗"
            tokens = f"{result['input_tokens']}in/{result['output_tokens']}out"
            print(f"\n  [{result['ticker']}] [{result['strategy']}] ({result['latency_ms']}ms) (format: {fmt}) (tokens: {tokens})")
            if result["hallucination_detected"]:
                print(f"  ⚠ Hallucination flags: {', '.join(result['flagged_terms'])}")
            print(f"  {result['analysis']}")
            print(f"  {'-' * 50}")

    print("\nResults saved to results.db")
    generate_report([r for r in results if r])


if __name__ == "__main__":
    asyncio.run(main())
