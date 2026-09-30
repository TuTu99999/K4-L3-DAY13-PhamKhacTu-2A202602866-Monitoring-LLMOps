from __future__ import annotations

import json
from datetime import datetime, timezone

from app import dashboard


def test_dashboard_snapshot_and_html_have_six_operational_panels(monkeypatch, tmp_path) -> None:
    log_path = tmp_path / "logs.jsonl"
    now = datetime.now(timezone.utc)
    records = [
        {
            "ts": now.isoformat(),
            "event": "request_received",
            "service": "api",
            "correlation_id": "req-12345678",
        },
        {
            "ts": now.isoformat(),
            "event": "response_sent",
            "service": "api",
            "correlation_id": "req-12345678",
            "latency_ms": 250,
            "ttft_ms": 50,
            "cost_usd": 0.002,
            "tokens_in": 30,
            "tokens_out": 100,
            "quality_score": 0.8,
            "tool_success": True,
        },
    ]
    log_path.write_text(
        "\n".join(json.dumps(record) for record in records) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(dashboard, "LOG_PATH", log_path)

    snapshot = dashboard.dashboard_snapshot(now)
    html = dashboard.render_dashboard(snapshot)

    assert snapshot["latency"]["p95"] == 250
    assert snapshot["errors"]["retrieval_success"] == 100
    assert snapshot["quality"]["average"] == 0.8
    assert html.count('<section class="card">') == 6
    assert "Time range: last 60 minutes" in html
    assert "refresh 30s" in html
    assert "SLO threshold" in html
