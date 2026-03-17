from flask import Flask, request, jsonify, send_from_directory, Response
from flask_cors import CORS
import os
import json
import time
import requests as req
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
client = Anthropic()

app = Flask(__name__, static_folder='.')
CORS(app)

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
    response = req.get(url, headers=headers, params=params)
    return response.json()

@app.route('/')
def home():
    return send_from_directory('.', 'index.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    data = request.json
    tickers = data.get('tickers', ['AAPL'])
    strategy = data.get('strategy', 'few_shot')

    def generate():
        for ticker in tickers:
            try:
                price_data = get_stock_data(ticker)
                bars = price_data.get("bars", [])
                if not bars:
                    yield f"data: {json.dumps({'ticker': ticker, 'error': 'No data available'})}\n\n"
                    continue

                prices = "\n".join([
                    f"Date: {b['t'][:10]}, Open: ${b['o']:.2f}, Close: ${b['c']:.2f}, Volume: {b['v']}"
                    for b in bars
                ])

                prompt = STRATEGIES[strategy](ticker, prices)
                start_time = time.time()
                full_response = ""

                yield f"data: {json.dumps({'ticker': ticker, 'status': 'analyzing'})}\n\n"

                with client.messages.stream(
                    model="claude-sonnet-4-20250514",
                    max_tokens=1000,
                    messages=[{"role": "user", "content": prompt}]
                ) as stream:
                    for text in stream.text_stream:
                        full_response += text
                        yield f"data: {json.dumps({'ticker': ticker, 'token': text})}\n\n"

                latency = round((time.time() - start_time) * 1000)
                signal = "BUY" if "BUY" in full_response else "SELL" if "SELL" in full_response else "HOLD"

                yield f"data: {json.dumps({'ticker': ticker, 'done': True, 'signal': signal, 'latency_ms': latency})}\n\n"

            except Exception as e:
                yield f"data: {json.dumps({'ticker': ticker, 'error': str(e)})}\n\n"

        yield f"data: {json.dumps({'complete': True})}\n\n"

    return Response(generate(), mimetype='text/event-stream',
                   headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})

if __name__ == '__main__':
    app.run(debug=True, port=5000)