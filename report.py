import json
from datetime import datetime


def generate_html_report():
    try:
        with open("results.json", "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        print("No results.json found. Run analyzer.py first.")
        return

    total_runs = sum(len(r["strategies"]) for r in data)
    correct_formats = sum(
        s["format_correct"] for r in data for s in r["strategies"]
    )
    format_accuracy = round((correct_formats / total_runs) * 100) if total_runs > 0 else 0

    avg_latency_by_strategy = {}
    for r in data:
        for s in r["strategies"]:
            name = s["strategy"]
            if name not in avg_latency_by_strategy:
                avg_latency_by_strategy[name] = []
            avg_latency_by_strategy[name].append(s["latency_ms"])

    latency_summary = " | ".join([
        f"{k}: {round(sum(v)/len(v))}ms avg"
        for k, v in avg_latency_by_strategy.items()
    ])

    rows = ""
    for r in data:
        for s in r["strategies"]:
            if "BUY" in s["analysis"]:
                signal = "<span style='color:#1D9E75;font-weight:500'>BUY</span>"
            elif "SELL" in s["analysis"]:
                signal = "<span style='color:#E24B4A;font-weight:500'>SELL</span>"
            else:
                signal = "<span style='color:#BA7517;font-weight:500'>HOLD</span>"

            rows += f"""
            <tr>
                <td>{r['ticker']}</td>
                <td><code>{s['strategy']}</code></td>
                <td>{s['latency_ms']}ms</td>
                <td>{'✓' if s['format_correct'] else '✗'}</td>
                <td>{signal}</td>
                <td style='font-size:12px;max-width:400px'>
                    {s['analysis'].replace(chr(10), '<br>')}
                </td>
            </tr>"""

    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Stock Analysis Report</title>
    <style>
        * {{ box-sizing: border-box; }}
        body {{ font-family: sans-serif; padding: 2rem; background: #f5f5f5; color: #1a1a1a; }}
        h1 {{ font-size: 22px; font-weight: 500; margin-bottom: 4px; }}
        .meta {{ color: #888; font-size: 13px; margin-bottom: 1.5rem; }}
        .latency-summary {{ font-size: 12px; color: #666; margin-bottom: 1.5rem; 
                           background: white; padding: 8px 14px; border-radius: 6px; 
                           display: inline-block; }}
        .summary {{ display: grid; grid-template-columns: repeat(3, 1fr); 
                   gap: 12px; margin-bottom: 2rem; }}
        .card {{ background: white; border-radius: 8px; padding: 1rem 1.25rem; }}
        .card-label {{ font-size: 12px; color: #888; margin-bottom: 4px; }}
        .card-value {{ font-size: 24px; font-weight: 500; }}
        table {{ width: 100%; border-collapse: collapse; background: white; 
                border-radius: 8px; overflow: hidden; }}
        th {{ background: #f1f0eb; padding: 12px 16px; text-align: left; 
             font-size: 12px; font-weight: 500; color: #555; 
             text-transform: uppercase; letter-spacing: 0.5px; }}
        td {{ padding: 12px 16px; font-size: 13px; 
             border-top: 1px solid #eee; vertical-align: top; }}
        tr:hover {{ background: #fafafa; }}
        code {{ background: #f1f0eb; padding: 2px 6px; border-radius: 4px; 
               font-size: 12px; }}
    </style>
</head>
<body>
    <h1>Stock Analysis — Prompting Strategy Comparison</h1>
    <div class="meta">Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}</div>
    <div class="latency-summary">{latency_summary}</div>

    <div class="summary">
        <div class="card">
            <div class="card-label">Tickers analyzed</div>
            <div class="card-value">{len(data)}</div>
        </div>
        <div class="card">
            <div class="card-label">Total strategy runs</div>
            <div class="card-value">{total_runs}</div>
        </div>
        <div class="card">
            <div class="card-label">Format accuracy</div>
            <div class="card-value">{format_accuracy}%</div>
        </div>
    </div>

    <table>
        <thead>
            <tr>
                <th>Ticker</th>
                <th>Strategy</th>
                <th>Latency</th>
                <th>Format</th>
                <th>Signal</th>
                <th>Analysis</th>
            </tr>
        </thead>
        <tbody>{rows}</tbody>
    </table>
</body>
</html>"""

    with open("report.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("Report saved to report.html — open it in your browser")


if __name__ == "__main__":
    generate_html_report()