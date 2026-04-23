from __future__ import annotations

import time
from typing import Any, AsyncGenerator

from anthropic import AsyncAnthropic
from dotenv import load_dotenv

load_dotenv()

client = AsyncAnthropic()

_MODEL = "claude-sonnet-4-20250514"

STRATEGIES: dict[str, Any] = {
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
SIGNAL: [BUY/HOLD/SELL] — [one sentence reasoning]""",

    # Two-turn conversation — handled by run_analysis / stream_analysis directly
    "self_critique": None,
}

_SELF_CRITIQUE_ROUND2 = (
    "Critique your reasoning above. Identify any flaws, unsupported assumptions, "
    "or missing context in your analysis. Revise your signal if needed.\n\n"
    "Format your final answer exactly as:\n"
    "TREND: [summary]\n"
    "OBSERVATIONS: [observations]\n"
    "SIGNAL: [BUY/HOLD/SELL] — [one sentence reasoning]"
)


async def _run_self_critique(
    ticker: str, prices: str
) -> tuple[str, int, int, int]:
    round1_prompt = STRATEGIES["few_shot"](ticker, prices)
    start = time.time()

    round1_msg = await client.messages.create(
        model=_MODEL,
        max_tokens=1000,
        messages=[{"role": "user", "content": round1_prompt}],
    )
    round1_text = round1_msg.content[0].text
    round1_signal = extract_signal(round1_text)

    round2_msg = await client.messages.create(
        model=_MODEL,
        max_tokens=1000,
        messages=[
            {"role": "user", "content": round1_prompt},
            {"role": "assistant", "content": round1_text},
            {"role": "user", "content": _SELF_CRITIQUE_ROUND2},
        ],
    )
    latency_ms = round((time.time() - start) * 1000)
    round2_text = round2_msg.content[0].text
    round2_signal = extract_signal(round2_text)

    header = f"[Round 1: {round1_signal}] → [Round 2: {round2_signal}]"
    if round1_signal != round2_signal:
        header += "  ⚠ signal changed"

    total_input = round1_msg.usage.input_tokens + round2_msg.usage.input_tokens
    total_output = round1_msg.usage.output_tokens + round2_msg.usage.output_tokens

    return f"{header}\n\n{round2_text}", latency_ms, total_input, total_output


async def _stream_self_critique(
    ticker: str, prices: str
) -> AsyncGenerator[str | dict, None]:
    round1_prompt = STRATEGIES["few_shot"](ticker, prices)
    round1_text = ""
    total_input = 0
    total_output = 0

    yield "[Round 1]\n"
    async with client.messages.stream(
        model=_MODEL,
        max_tokens=1000,
        messages=[{"role": "user", "content": round1_prompt}],
    ) as stream:
        async for text in stream.text_stream:
            round1_text += text
            yield text
        final1 = await stream.get_final_message()
        total_input += final1.usage.input_tokens
        total_output += final1.usage.output_tokens

    round1_signal = extract_signal(round1_text)

    yield "\n\n[Round 2 — Self-Critique]\n"
    round2_text = ""
    async with client.messages.stream(
        model=_MODEL,
        max_tokens=1000,
        messages=[
            {"role": "user", "content": round1_prompt},
            {"role": "assistant", "content": round1_text},
            {"role": "user", "content": _SELF_CRITIQUE_ROUND2},
        ],
    ) as stream:
        async for text in stream.text_stream:
            round2_text += text
            yield text
        final2 = await stream.get_final_message()
        total_input += final2.usage.input_tokens
        total_output += final2.usage.output_tokens

    round2_signal = extract_signal(round2_text)
    if round1_signal != round2_signal:
        yield f"\n\n⚠ Signal changed: {round1_signal} → {round2_signal}"

    yield {"input_tokens": total_input, "output_tokens": total_output}


async def stream_analysis(
    ticker: str, prices: str, strategy_name: str
) -> AsyncGenerator[str | dict, None]:
    if strategy_name == "self_critique":
        async for chunk in _stream_self_critique(ticker, prices):
            yield chunk
        return

    prompt = STRATEGIES[strategy_name](ticker, prices)
    async with client.messages.stream(
        model=_MODEL,
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        async for text in stream.text_stream:
            yield text
        final = await stream.get_final_message()
        yield {"input_tokens": final.usage.input_tokens, "output_tokens": final.usage.output_tokens}


async def run_analysis(
    ticker: str, prices: str, strategy_name: str
) -> tuple[str, int, int, int]:
    if strategy_name == "self_critique":
        return await _run_self_critique(ticker, prices)

    prompt = STRATEGIES[strategy_name](ticker, prices)
    start = time.time()
    message = await client.messages.create(
        model=_MODEL,
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}],
    )
    latency_ms = round((time.time() - start) * 1000)
    return (
        message.content[0].text,
        latency_ms,
        message.usage.input_tokens,
        message.usage.output_tokens,
    )


def extract_signal(text: str) -> str:
    if "BUY" in text:
        return "BUY"
    if "SELL" in text:
        return "SELL"
    return "HOLD"


def check_format(text: str) -> bool:
    return all(field in text for field in ["TREND:", "OBSERVATIONS:", "SIGNAL:"])
