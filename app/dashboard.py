from __future__ import annotations

import json
import os
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path
from statistics import mean
from typing import Any

import yaml
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from .metrics import percentile


LOG_PATH = Path(os.getenv("LOG_PATH", "data/logs.jsonl"))
CONFIG_PATH = Path("config/dashboard.yaml")


def _read_records(now: datetime | None = None) -> list[dict[str, Any]]:
    if not LOG_PATH.exists():
        return []
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(minutes=60)
    records: list[dict[str, Any]] = []
    for line in LOG_PATH.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(line)
            timestamp = datetime.fromisoformat(record["ts"].replace("Z", "+00:00"))
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            continue
        if timestamp >= cutoff:
            record["_timestamp"] = timestamp
            records.append(record)
    return records


def _minute_series(
    records: list[dict[str, Any]],
    field: str,
    event: str,
    aggregation: str = "sum",
) -> list[float]:
    buckets: dict[str, list[float]] = defaultdict(list)
    for record in records:
        if record.get("event") == event and isinstance(record.get(field), (int, float)):
            minute = record["_timestamp"].strftime("%H:%M")
            buckets[minute].append(float(record[field]))
    if aggregation == "mean":
        return [mean(buckets[key]) for key in sorted(buckets)] or [0.0]
    if aggregation == "p95":
        return [percentile([int(value) for value in buckets[key]], 95) for key in sorted(buckets)] or [0.0]
    return [sum(buckets[key]) for key in sorted(buckets)] or [0.0]


def _error_rate_series(records: list[dict[str, Any]]) -> list[float]:
    totals: Counter[str] = Counter()
    failures: Counter[str] = Counter()
    for record in records:
        minute = record["_timestamp"].strftime("%H:%M")
        if record.get("event") == "request_received":
            totals[minute] += 1
        elif record.get("event") == "request_failed":
            failures[minute] += 1
    return [100 * failures[key] / totals[key] for key in sorted(totals)] or [0.0]


def dashboard_snapshot(now: datetime | None = None) -> dict[str, Any]:
    records = _read_records(now)
    requests = [r for r in records if r.get("event") == "request_received"]
    responses = [r for r in records if r.get("event") == "response_sent"]
    failures = [r for r in records if r.get("event") == "request_failed"]
    latencies = [int(r["latency_ms"]) for r in responses if isinstance(r.get("latency_ms"), int)]
    ttfts = [int(r["ttft_ms"]) for r in responses if isinstance(r.get("ttft_ms"), int)]
    costs = [float(r["cost_usd"]) for r in responses if isinstance(r.get("cost_usd"), (int, float))]
    qualities = [float(r["quality_score"]) for r in responses if isinstance(r.get("quality_score"), (int, float))]
    tool_events = [r for r in records if isinstance(r.get("tool_success"), bool)]
    retrieval_success = (
        100 * sum(r["tool_success"] is True for r in tool_events) / len(tool_events)
        if tool_events
        else 0.0
    )
    error_rate = 100 * len(failures) / len(requests) if requests else 0.0
    error_breakdown = Counter(str(r.get("error_type") or "unknown") for r in failures)
    challenge_responses = [
        r
        for r in responses
        if str(r.get("session_id", "")).startswith("k4-l3b-challenge-")
    ]
    baseline_responses = [r for r in responses if r not in challenge_responses]
    challenge_latencies = [int(r["latency_ms"]) for r in challenge_responses]
    baseline_latencies = [int(r["latency_ms"]) for r in baseline_responses]
    baseline_p95 = percentile(baseline_latencies, 95)
    challenge_p95 = percentile(challenge_latencies, 95)
    delta_pct = (
        round((challenge_p95 - baseline_p95) / baseline_p95 * 100, 1)
        if baseline_p95 and challenge_latencies
        else 0.0
    )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "record_count": len(records),
        "latency": {
            "p50": percentile(latencies, 50),
            "p95": percentile(latencies, 95),
            "p99": percentile(latencies, 99),
            "ttft_p95": percentile(ttfts, 95),
            "series": _minute_series(records, "latency_ms", "response_sent", "p95"),
        },
        "traffic": {
            "count": len(requests),
            "rpm": round(len(requests) / 60, 2),
            "series": _minute_series(
                [{**r, "request_count": 1} for r in requests],
                "request_count",
                "request_received",
            ),
        },
        "errors": {
            "rate": round(error_rate, 2),
            "retrieval_success": round(retrieval_success, 2),
            "breakdown": dict(error_breakdown),
            "series": _error_rate_series(records),
        },
        "cost": {
            "total": round(sum(costs), 6),
            "series": _minute_series(records, "cost_usd", "response_sent"),
        },
        "tokens": {
            "input": sum(int(r.get("tokens_in", 0)) for r in responses),
            "output": sum(int(r.get("tokens_out", 0)) for r in responses),
            "series": _minute_series(records, "tokens_out", "response_sent"),
        },
        "quality": {
            "average": round(mean(qualities), 3) if qualities else 0.0,
            "series": _minute_series(records, "quality_score", "response_sent", "mean"),
        },
        "incident_comparison": {
            "baseline_p95": baseline_p95,
            "challenge_p95": challenge_p95,
            "delta_pct": delta_pct,
            "challenge_count": len(challenge_responses),
            "start_utc": (
                min(r["_timestamp"] for r in challenge_responses).strftime("%H:%M:%S")
                if challenge_responses
                else None
            ),
            "end_utc": (
                max(r["_timestamp"] for r in challenge_responses).strftime("%H:%M:%S")
                if challenge_responses
                else None
            ),
        },
    }


def _thresholds() -> dict[str, dict[str, Any]]:
    payload = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    return {
        panel["id"]: panel["threshold"]
        for panel in payload["dashboard"]["panels"]
    }


def _chart(values: list[float], threshold: float) -> str:
    visible = values[-20:]
    ceiling = max([threshold, *visible, 0.000001])
    bars = "".join(
        f'<span style="height:{max(3, min(100, value / ceiling * 100)):.1f}%"></span>'
        for value in visible
    )
    threshold_position = max(0, min(100, 100 - threshold / ceiling * 100))
    return (
        '<div class="chart">'
        f'<div class="threshold" style="top:{threshold_position:.1f}%"></div>{bars}'
        "</div>"
    )


def _card(title: str, metric: str, detail: str, unit: str, threshold: str, chart: str) -> str:
    return f"""
      <section class="card">
        <div class="card-head"><h2>{escape(title)}</h2><span>{escape(unit)}</span></div>
        <div class="metric">{escape(metric)}</div>
        <p>{escape(detail)}</p>
        {chart}
        <div class="threshold-label">SLO threshold: {escape(threshold)}</div>
      </section>
    """


def render_dashboard(snapshot: dict[str, Any]) -> str:
    threshold = _thresholds()
    latency = snapshot["latency"]
    traffic = snapshot["traffic"]
    errors = snapshot["errors"]
    cost = snapshot["cost"]
    tokens = snapshot["tokens"]
    quality = snapshot["quality"]
    incident = snapshot["incident_comparison"]
    incident_banner = ""
    if incident["challenge_count"]:
        incident_banner = f"""
        <section class="incident">
          <strong>Challenge latency anomaly</strong>
          <span>P95 {incident['baseline_p95']:.0f} ms baseline → {incident['challenge_p95']:.0f} ms challenge
          ({incident['delta_pct']:+.1f}%) · {incident['challenge_count']} requests ·
          {escape(incident['start_utc'])}–{escape(incident['end_utc'])} UTC</span>
        </section>
        """
    cards = [
        _card(
            "Latency percentiles and TTFT",
            f"P95 {latency['p95']:.0f} ms",
            f"P50 {latency['p50']:.0f} · P99 {latency['p99']:.0f} · TTFT P95 {latency['ttft_p95']:.0f}",
            "milliseconds",
            "P95 ≤ 3000 ms",
            _chart(latency["series"], float(threshold["latency"]["value"])),
        ),
        _card(
            "Request traffic",
            f"{traffic['count']} requests",
            f"Average {traffic['rpm']:.2f} requests/minute over the 60-minute window",
            "requests / minute",
            "rate ≥ 1 request/minute",
            _chart(traffic["series"], float(threshold["traffic"]["value"])),
        ),
        _card(
            "Error rate and retrieval success",
            f"{errors['rate']:.2f}% errors",
            f"Retrieval success {errors['retrieval_success']:.2f}% · breakdown {errors['breakdown'] or 'none'}",
            "percent",
            "error rate ≤ 2%",
            _chart(errors["series"], float(threshold["errors"]["value"])),
        ),
        _card(
            "Cost over time",
            f"${cost['total']:.4f}",
            "Estimated input and output token cost in the current window",
            "USD",
            "total ≤ $2.50",
            _chart(cost["series"], float(threshold["cost"]["value"])),
        ),
        _card(
            "Input and output tokens",
            f"{tokens['input'] + tokens['output']:,} tokens",
            f"Input {tokens['input']:,} · Output {tokens['output']:,}",
            "tokens",
            "combined total ≤ 50,000",
            _chart(tokens["series"], float(threshold["tokens"]["value"])),
        ),
        _card(
            "Quality proxy",
            f"{quality['average']:.3f}",
            "Mean heuristic quality score for successful responses",
            "score 0–1",
            "mean ≥ 0.75",
            _chart(quality["series"], float(threshold["quality"]["value"])),
        ),
    ]
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<meta http-equiv="refresh" content="30"><title>Day 13 LLMOps Dashboard</title>
<style>
:root{{--bg:#07111f;--panel:#101d2f;--ink:#eef6ff;--muted:#96a9bf;--cyan:#43d6c6;--amber:#ffca69;--line:#ff6b81}}
*{{box-sizing:border-box}} body{{margin:0;background:radial-gradient(circle at top left,#16304c,var(--bg) 42%);color:var(--ink);font:15px/1.45 Inter,Segoe UI,sans-serif;min-height:100vh}}
main{{max-width:1280px;margin:auto;padding:30px}} header{{display:flex;justify-content:space-between;align-items:end;margin-bottom:22px}} h1{{font-size:30px;margin:0}} header p,.card p{{color:var(--muted);margin:5px 0}} .status{{border:1px solid #28516a;border-radius:999px;padding:8px 13px;color:var(--cyan)}}
.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}} .card{{background:linear-gradient(145deg,rgba(19,38,59,.98),rgba(11,25,42,.98));border:1px solid #233b54;border-radius:16px;padding:18px;box-shadow:0 15px 35px #0004}}
.incident{{display:flex;justify-content:space-between;gap:16px;margin:-6px 0 18px;padding:12px 16px;border:1px solid #b6752d;border-radius:12px;background:#3b2917;color:#ffd797}} .incident span{{text-align:right}}
.card-head{{display:flex;justify-content:space-between;gap:10px}} h2{{font-size:15px;margin:0}} .card-head span{{color:var(--muted);font-size:12px}} .metric{{font-size:30px;font-weight:750;margin:12px 0 2px;color:var(--cyan)}}
.chart{{height:82px;display:flex;align-items:end;gap:5px;position:relative;border-bottom:1px solid #35506a;margin:16px 0 8px;overflow:hidden}} .chart span{{flex:1;min-width:4px;background:linear-gradient(var(--cyan),#227fa0);border-radius:4px 4px 0 0;opacity:.85}} .threshold{{position:absolute;left:0;right:0;border-top:2px dashed var(--line);z-index:2}}
.threshold-label{{font-size:12px;color:var(--amber)}} footer{{color:var(--muted);font-size:12px;margin-top:18px}} @media(max-width:900px){{.grid{{grid-template-columns:1fr 1fr}}}} @media(max-width:600px){{.grid{{grid-template-columns:1fr}}}}
</style></head><body><main><header><div><h1>Monitoring & LLMOps</h1><p>Operational view from data/logs.jsonl</p></div><div class="status">● Live · refresh 30s</div></header>
{incident_banner}<div class="grid">{''.join(cards)}</div><footer>Time range: last 60 minutes (UTC) · {snapshot['record_count']} records · generated {escape(snapshot['generated_at'])}</footer>
</main></body></html>"""


app = FastAPI(title="Day 13 Monitoring Dashboard")


@app.get("/", response_class=HTMLResponse)
async def dashboard() -> HTMLResponse:
    return HTMLResponse(render_dashboard(dashboard_snapshot()))


@app.get("/api/dashboard")
async def dashboard_data() -> dict[str, Any]:
    return dashboard_snapshot()
