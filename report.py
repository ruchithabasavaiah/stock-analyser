from __future__ import annotations

from datetime import datetime

import httpx


def fetch_from_api() -> tuple[list[dict] | None, dict | None]:
    try:
        with httpx.Client(timeout=5.0) as client:
            results_resp = client.get("http://localhost:8000/api/results")
            summary_resp = client.get("http://localhost:8000/api/results/summary")
            results_resp.raise_for_status()
            summary_resp.raise_for_status()
            return results_resp.json(), summary_resp.json()
    except Exception:
        return None, None


def fetch_from_db() -> tuple[list[dict], None]:
    from api.db import create_db, get_all_results

    create_db()
    records = get_all_results()
    return [
        {
            "ticker": r.ticker,
            "strategy": r.strategy,
            "signal": r.signal,
            "latency_ms": r.latency_ms,
            "format_correct": r.format_correct,
            "analysis": r.analysis,
            "input_tokens": r.input_tokens,
            "output_tokens": r.output_tokens,
            "hallucination_detected": r.hallucination_detected,
            "flagged_terms": r.flagged_terms,
            "consistency_pct": r.consistency_pct,
            "is_consistent": r.is_consistent,
        }
        for r in records
    ], None


def compute_latency_summary(records: list[dict]) -> str:
    by_strategy: dict[str, list[int]] = {}
    for r in records:
        by_strategy.setdefault(r["strategy"], []).append(r["latency_ms"])
    return " | ".join([
        f"{k}: {round(sum(v) / len(v))}ms avg"
        for k, v in by_strategy.items()
    ])


def _build_main_rows(results: list[dict]) -> str:
    rows = ""
    for r in results:
        sig = r["signal"]
        if sig == "BUY":
            signal_html = "<span style='color:#1D9E75;font-weight:500'>BUY</span>"
        elif sig == "SELL":
            signal_html = "<span style='color:#E24B4A;font-weight:500'>SELL</span>"
        else:
            signal_html = "<span style='color:#BA7517;font-weight:500'>HOLD</span>"

        inp = r.get("input_tokens") or 0
        out = r.get("output_tokens") or 0
        tokens_display = f"{inp:,}&thinsp;/&thinsp;{out:,}" if inp > 0 else "—"

        raw_terms = r.get("flagged_terms") or []
        if isinstance(raw_terms, list):
            terms = raw_terms
        else:
            terms = [t.strip() for t in raw_terms.split(",") if t.strip()]
        flags_display = ", ".join(terms) if terms else "—"
        row_style = "background:#fff8f8;" if r.get("hallucination_detected") and terms else ""

        rows += f"""
            <tr style='{row_style}'>
                <td>{r['ticker']}</td>
                <td><code>{r['strategy']}</code></td>
                <td>{r['latency_ms']}ms</td>
                <td>{'✓' if r['format_correct'] else '✗'}</td>
                <td>{signal_html}</td>
                <td style='white-space:nowrap'>{tokens_display}</td>
                <td>{flags_display}</td>
                <td style='font-size:12px;max-width:380px'>
                    {r['analysis'].replace(chr(10), '<br>')}
                </td>
            </tr>"""
    return rows


def _build_token_section(results: list[dict]) -> str:
    by_strategy: dict[str, dict] = {}
    for r in results:
        s = r.get("strategy", "")
        if s not in by_strategy:
            by_strategy[s] = {"input": [], "output": []}
        inp = r.get("input_tokens") or 0
        out = r.get("output_tokens") or 0
        if inp > 0:
            by_strategy[s]["input"].append(inp)
            by_strategy[s]["output"].append(out)

    token_rows = ""
    for strategy, data in by_strategy.items():
        if not data["input"]:
            continue
        avg_in = round(sum(data["input"]) / len(data["input"]))
        avg_out = round(sum(data["output"]) / len(data["output"]))
        token_rows += f"""
            <tr>
                <td><code>{strategy}</code></td>
                <td>{avg_in:,}</td>
                <td>{avg_out:,}</td>
                <td>{avg_in + avg_out:,}</td>
            </tr>"""

    if not token_rows:
        return ""

    return f"""
    <h2 class="section-title">Token Efficiency</h2>
    <table>
        <thead>
            <tr>
                <th>Strategy</th>
                <th>Avg Input Tokens</th>
                <th>Avg Output Tokens</th>
                <th>Avg Total</th>
            </tr>
        </thead>
        <tbody>{token_rows}</tbody>
    </table>"""


def _build_consistency_section(results: list[dict]) -> str:
    seen: dict[tuple, dict] = {}
    for r in results:
        cpct = r.get("consistency_pct")
        if cpct is not None:
            key = (r["ticker"], r["strategy"])
            seen[key] = {"consistency_pct": cpct, "is_consistent": r.get("is_consistent")}

    if not seen:
        return """
    <h2 class="section-title">Consistency Scores</h2>
    <p class="no-data">No consistency data yet — run <code>POST /api/evaluate</code> to generate.</p>"""

    consistency_rows = ""
    for (ticker, strategy), data in seen.items():
        color = "#1D9E75" if data["is_consistent"] else "#E24B4A"
        consistency_rows += f"""
            <tr>
                <td>{ticker}</td>
                <td><code>{strategy}</code></td>
                <td style='color:{color};font-weight:500'>{data['consistency_pct']}%</td>
                <td>{'✓' if data['is_consistent'] else '✗'}</td>
            </tr>"""

    return f"""
    <h2 class="section-title">Consistency Scores</h2>
    <table>
        <thead>
            <tr>
                <th>Ticker</th>
                <th>Strategy</th>
                <th>Consistency</th>
                <th>All Agree?</th>
            </tr>
        </thead>
        <tbody>{consistency_rows}</tbody>
    </table>"""


def generate_report(results: list[dict]) -> None:
    if not results:
        print("No results to report.")
        return

    total_runs = len(results)
    tickers = list({r["ticker"] for r in results})
    correct_formats = sum(1 for r in results if r["format_correct"])
    format_accuracy = round((correct_formats / total_runs) * 100) if total_runs > 0 else 0
    latency_summary = compute_latency_summary(results)

    main_rows = _build_main_rows(results)
    token_section = _build_token_section(results)
    consistency_section = _build_consistency_section(results)

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Stock Analysis Report</title>
    <style>
        * {{ box-sizing: border-box; }}
        body {{ font-family: sans-serif; padding: 2rem; background: #f5f5f5; color: #1a1a1a; }}
        h1 {{ font-size: 22px; font-weight: 500; margin-bottom: 4px; }}
        .section-title {{ font-size: 17px; font-weight: 500; margin: 2.5rem 0 1rem; }}
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
                border-radius: 8px; overflow: hidden; margin-bottom: 1rem; }}
        th {{ background: #f1f0eb; padding: 12px 16px; text-align: left;
             font-size: 12px; font-weight: 500; color: #555;
             text-transform: uppercase; letter-spacing: 0.5px; }}
        td {{ padding: 12px 16px; font-size: 13px;
             border-top: 1px solid #eee; vertical-align: top; }}
        tr:hover {{ background: #fafafa; }}
        code {{ background: #f1f0eb; padding: 2px 6px; border-radius: 4px;
               font-size: 12px; }}
        .no-data {{ color: #999; font-size: 13px; font-style: italic; }}
    </style>
</head>
<body>
    <h1>Stock Analysis — Prompting Strategy Comparison</h1>
    <div class="meta">Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}</div>
    <div class="latency-summary">{latency_summary}</div>

    <div class="summary">
        <div class="card">
            <div class="card-label">Tickers analyzed</div>
            <div class="card-value">{len(tickers)}</div>
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
                <th>Tokens (in/out)</th>
                <th>Flags</th>
                <th>Analysis</th>
            </tr>
        </thead>
        <tbody>{main_rows}</tbody>
    </table>

    {token_section}
    {consistency_section}
</body>
</html>"""

    with open("report.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("Report saved to report.html — open it in your browser")


def generate_html_report() -> None:
    results, _ = fetch_from_api()

    if results is None:
        print("Server not running — reading from DB directly...")
        results, _ = fetch_from_db()

    generate_report(results or [])


if __name__ == "__main__":
    generate_html_report()
