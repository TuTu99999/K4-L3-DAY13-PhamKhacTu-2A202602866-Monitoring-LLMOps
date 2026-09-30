from __future__ import annotations

from app import mock_llm, mock_rag


class RecordingClient:
    def __init__(self) -> None:
        self.span_updates: list[dict] = []
        self.generation_updates: list[dict] = []

    def update_current_span(self, **kwargs) -> None:
        self.span_updates.append(kwargs)

    def update_current_generation(self, **kwargs) -> None:
        self.generation_updates.append(kwargs)


def test_retrieval_records_only_sanitized_metadata(monkeypatch) -> None:
    client = RecordingClient()
    monkeypatch.setattr(mock_rag, "get_langfuse_client", lambda: client)

    docs = mock_rag.retrieve.__wrapped__("refund for student@example.com")

    assert docs
    metadata = client.span_updates[-1]["metadata"]
    assert metadata["doc_count"] == 1
    assert "student@example.com" not in metadata["query_preview"]
    assert "REDACTED_EMAIL" in metadata["query_preview"]


def test_generation_records_model_usage_cost_and_ttft(monkeypatch) -> None:
    client = RecordingClient()
    monkeypatch.setattr(mock_llm, "get_langfuse_client", lambda: client)

    response = mock_llm.FakeLLM().generate.__wrapped__(mock_llm.FakeLLM(), "safe prompt")

    update = client.generation_updates[-1]
    assert update["model"] == response.model
    assert update["usage_details"]["input"] == response.usage.input_tokens
    assert update["usage_details"]["output"] == response.usage.output_tokens
    assert update["usage_details"]["total"] == (
        response.usage.input_tokens + response.usage.output_tokens
    )
    assert update["cost_details"]["total"] > 0
    assert update["metadata"]["ttft_ms"] == response.ttft_ms
    assert "input" not in update
    assert "output" not in update
