from __future__ import annotations

import asyncio

from api.services.claude import extract_signal, run_analysis

_HALLUCINATION_TERMS = [
    "earnings",
    "dividend",
    "analyst",
    "rating",
    "upgrade",
    "downgrade",
    "news",
    "ceo",
    "guidance",
    "forecast",
    "beat",
    "miss",
    "revenue",
    "profit",
    "loss",
    "outlook",
    "eps",
    "quarterly report",
    "announcement",
    "press release",
]


async def consistency_score(
    ticker: str, prices: str, strategy: str, runs: int = 3
) -> dict:
    raw = await asyncio.gather(
        *[run_analysis(ticker, prices, strategy) for _ in range(runs)]
    )
    signals = [extract_signal(r[0]) for r in raw]
    majority = max(set(signals), key=signals.count)
    consistency_pct = round(signals.count(majority) / runs * 100, 1)
    is_consistent = len(set(signals)) == 1

    return {
        "signals": signals,
        "consistency_pct": consistency_pct,
        "majority_signal": majority,
        "is_consistent": is_consistent,
        "results": [
            {
                "analysis": r[0],
                "latency_ms": r[1],
                "input_tokens": r[2],
                "output_tokens": r[3],
            }
            for r in raw
        ],
    }


def detect_hallucination(analysis: str, prices_context: str) -> dict:
    lower = analysis.lower()
    flagged = [term for term in _HALLUCINATION_TERMS if term in lower]
    return {
        "hallucination_detected": bool(flagged),
        "flagged_terms": flagged,
    }
