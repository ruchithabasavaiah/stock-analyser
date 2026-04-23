from __future__ import annotations

import json
import time

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from api.db import save_result
from api.models.schemas import AnalyzeRequest
from api.services.alpaca import format_bars, get_stock_data
from api.services.claude import STRATEGIES, check_format, extract_signal, stream_analysis
from api.services.evaluator import detect_hallucination

router = APIRouter()


@router.post("/analyze")
async def analyze(request: AnalyzeRequest):
    async def generate():
        strategies_to_run = (
            list(STRATEGIES.keys()) if request.strategy == "all" else [request.strategy]
        )

        for ticker in request.tickers:
            try:
                price_data = await get_stock_data(ticker)
                bars = price_data.get("bars", [])
                if not bars:
                    yield f"data: {json.dumps({'ticker': ticker, 'error': 'No data available'})}\n\n"
                    continue

                prices = format_bars(bars)

                for strategy_name in strategies_to_run:
                    yield f"data: {json.dumps({'ticker': ticker, 'strategy': strategy_name, 'status': 'analyzing'})}\n\n"

                    full_response = ""
                    input_tokens = 0
                    output_tokens = 0
                    start_time = time.time()

                    try:
                        async for chunk in stream_analysis(ticker, prices, strategy_name):
                            if isinstance(chunk, dict):
                                input_tokens = chunk["input_tokens"]
                                output_tokens = chunk["output_tokens"]
                            else:
                                full_response += chunk
                                yield f"data: {json.dumps({'ticker': ticker, 'strategy': strategy_name, 'token': chunk})}\n\n"

                        latency = round((time.time() - start_time) * 1000)
                        signal = extract_signal(full_response)
                        format_correct = check_format(full_response)
                        hall = detect_hallucination(full_response, prices)

                        save_result(
                            ticker, strategy_name, signal, latency, format_correct, full_response,
                            input_tokens=input_tokens,
                            output_tokens=output_tokens,
                            hallucination_detected=hall["hallucination_detected"],
                            flagged_terms=",".join(hall["flagged_terms"]),
                        )

                        yield f"data: {json.dumps({'ticker': ticker, 'strategy': strategy_name, 'done': True, 'signal': signal, 'latency_ms': latency, 'input_tokens': input_tokens, 'output_tokens': output_tokens, 'hallucination_detected': hall['hallucination_detected']})}\n\n"

                    except Exception as e:
                        yield f"data: {json.dumps({'ticker': ticker, 'strategy': strategy_name, 'error': str(e)})}\n\n"

            except Exception as e:
                yield f"data: {json.dumps({'ticker': ticker, 'error': str(e)})}\n\n"

        yield f"data: {json.dumps({'complete': True})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
