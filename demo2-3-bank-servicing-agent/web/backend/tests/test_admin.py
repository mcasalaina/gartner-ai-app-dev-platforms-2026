from __future__ import annotations

from bank_servicing_backend.stores import QualityMetricsSnapshot


def test_admin_metrics_returns_explicit_nulls_when_unavailable(client) -> None:
    test_client, _foundry, _obo, _voice = client

    response = test_client.get(
        "/api/admin/metrics",
        headers={"Authorization": "Bearer ignored"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "comprehensiveness": None,
        "accuracy": None,
        "latencyP50Ms": None,
        "estimatedCostUsd": None,
    }


def test_quality_snapshot_reports_observed_chat_latency() -> None:
    snapshot = QualityMetricsSnapshot()

    snapshot.record_latency(14.5)
    snapshot.record_latency(20.5)

    assert snapshot.latency_p50_ms == 17.5


def test_review_queue_and_decision_endpoints(client) -> None:
    test_client, _foundry, _obo, _voice = client

    queue = test_client.get(
        "/api/admin/content/reviews",
        headers={"Authorization": "Bearer ignored"},
    )
    decision = test_client.post(
        "/api/admin/content/reviews/draft-synthetic-001/approve",
        headers={"Authorization": "Bearer ignored"},
    )

    assert queue.status_code == 200
    assert queue.json()[0]["status"] == "pending_review"
    assert decision.status_code == 200
    assert decision.json()["status"] == "approved"
    assert decision.json()["version"] == 4


def test_model_compare_uses_allowlisted_candidates(client) -> None:
    test_client, foundry, _obo, _voice = client

    response = test_client.post(
        "/api/admin/evaluations/compare",
        headers={"Authorization": "Bearer ignored", "x-client-demo-mode": "service_discovery"},
        json={"prompt": "Synthetic prompt"},
    )

    assert response.status_code == 200
    models = [item["model"] for item in response.json()]
    assert models == ["gpt-5.4-mini", "gpt-5-mini", "gpt-4.1-mini"]
    assert [call["model_override"] for call in foundry.calls] == models
    assert response.json()[0]["rubricScore"] is None
    assert response.json()[0]["assertScore"] is None
