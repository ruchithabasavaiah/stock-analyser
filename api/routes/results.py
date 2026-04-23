from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException

from api.db import get_all_results, get_results_by_ticker, save_result
from api.models.schemas import EvaluateRequest
from api.services.alpaca import format_bars, get_stock_data
from api.services.claude import check_format, extract_signal
from api.services.evaluator import consistency_score, detect_hallucination

router = APIRouter()


@router.get("/results/summary")
async def get_summary():
    records = get_all_results()
    strategy_stats: dict[str, dict] = {}

    for r in records:
        if r.strategy not in strategy_stats:
            strategy_stats[r.strategy] = {
                "latencies": [],
                "format_correct_count": 0,
                "total": 0,
                "signals": {"BUY": 0, "HOLD": 0, "SELL": 0},
            }
        s = strategy_stats[r.strategy]
        s["latencies"].append(r.latency_ms)
        s["total"] += 1
        if r.format_correct:
            s["format_correct_count"] += 1
        if r.signal in s["signals"]:
            s["signals"][r.signal] += 1

    return {
        strategy: {
            "avg_latency_ms": round(sum(s["latencies"]) / len(s["latencies"])) if s["latencies"] else 0,
            "format_accuracy_pct": round((s["format_correct_count"] / s["total"]) * 100) if s["total"] > 0 else 0,
            "signal_distribution": s["signals"],
            "total_runs": s["total"],
        }
        for strategy, s in strategy_stats.items()
    }


@router.get("/results")
async def get_results(ticker: Optional[str] = None):
    if ticker:
        records = get_results_by_ticker(ticker.upper())
    else:
        records = get_all_results()
    return records


@router.post("/evaluate")
async def evaluate(request: EvaluateRequest):
    price_data = await get_stock_data(request.ticker)
    bars = price_data.get("bars", [])
    if not bars:
        raise HTTPException(status_code=404, detail=f"No price data available for {request.ticker}")

    prices = format_bars(bars)
    consistency = await consistency_score(request.ticker, prices, request.strategy, request.runs)

    run_reports = []
    for i, run in enumerate(consistency["results"]):
        signal = consistency["signals"][i]
        hall = detect_hallucination(run["analysis"], prices)
        fmt_correct = check_format(run["analysis"])

        save_result(
            request.ticker,
            request.strategy,
            signal,
            run["latency_ms"],
            fmt_correct,
            run["analysis"],
            input_tokens=run["input_tokens"],
            output_tokens=run["output_tokens"],
            hallucination_detected=hall["hallucination_detected"],
            flagged_terms=",".join(hall["flagged_terms"]),
            consistency_pct=consistency["consistency_pct"],
            is_consistent=consistency["is_consistent"],
        )

        run_reports.append({
            "run": i + 1,
            "signal": signal,
            "latency_ms": run["latency_ms"],
            "input_tokens": run["input_tokens"],
            "output_tokens": run["output_tokens"],
            "format_correct": fmt_correct,
            "hallucination_detected": hall["hallucination_detected"],
            "flagged_terms": hall["flagged_terms"],
        })

    return {
        "ticker": request.ticker,
        "strategy": request.strategy,
        "runs": request.runs,
        "consistency": {
            "signals": consistency["signals"],
            "consistency_pct": consistency["consistency_pct"],
            "majority_signal": consistency["majority_signal"],
            "is_consistent": consistency["is_consistent"],
        },
        "run_reports": run_reports,
    }
