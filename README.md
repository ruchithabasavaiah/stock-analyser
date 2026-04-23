# Stock Analyzer — LLM Prompting Benchmarker

An AI-powered tool that doesn't just analyze stocks — it evaluates *how* you 
prompt the model and measures whether better prompting produces better results.

## What It Does

Fetches live market data and runs it through four Claude prompting strategies 
simultaneously, then benchmarks the results across signal quality, token cost, 
consistency, and hallucination rate.

## Why It's Different

Most AI projects just call an LLM and display the output. This one treats 
prompt engineering as an engineering problem — something you can test, measure, 
and optimize.

## Strategies Compared

| Strategy | Approach |
|---|---|
| `zero_shot` | Direct analysis, no guidance |
| `few_shot` | Learns from a worked example |
| `chain_of_thought` | Forced step-by-step reasoning |
| `self_critique` | Generates a signal, then critiques and revises it |

## What Gets Measured

- Signal consistency across multiple runs
- Token cost per strategy
- Hallucination detection — did Claude use data not in the prompt?
- Format compliance and latency

## Tech Stack

FastAPI · Claude API (SSE streaming) · Alpaca Markets · SQLModel · Pydantic · Python 3.11

## Run It

```bash
pip install -r requirements.txt
uvicorn api.main:app --reload
# or
python analyzer.py --ticker AAPL TSLA --strategy all
```