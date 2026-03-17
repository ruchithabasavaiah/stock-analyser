from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
from analyzer import get_stock_data, analyze_stock, check_format

app = Flask(__name__, static_folder='.')
CORS(app)

@app.route('/')
def home():
    return send_from_directory('.', 'index.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    data = request.json
    tickers = data.get('tickers', ['AAPL'])
    strategy = data.get('strategy', 'few_shot')
    
    results = []
    for ticker in tickers:
        price_data = get_stock_data(ticker)
        analysis, latency = analyze_stock(ticker, price_data, strategy)
        if analysis:
            signal = "BUY" if "BUY" in analysis else "SELL" if "SELL" in analysis else "HOLD"
            results.append({
                "ticker": ticker,
                "signal": signal,
                "analysis": analysis,
                "latency_ms": latency,
                "format_correct": check_format(analysis)
            })
    
    return jsonify(results)

if __name__ == '__main__':
    app.run(debug=True, port=5000)