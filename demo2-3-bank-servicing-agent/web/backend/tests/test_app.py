from __future__ import annotations

from fastapi.testclient import TestClient

from bank_servicing_backend.app import RequestMetrics, create_app
from bank_servicing_backend.auth import AuthenticatedPrincipal
from bank_servicing_backend.config import AppSettings
from bank_servicing_backend.stores import InMemoryConversationStore, InMemoryReviewStore, QualityMetricsSnapshot
from bank_servicing_backend.voice import InMemoryVoiceHandleStore

from .conftest import FakeFoundryClient, FakeOboProvider, FakeValidator, FakeVoiceClient


def test_chat_compatibility_shape_and_allowlisted_headers(client) -> None:
    test_client, foundry, _obo, _voice = client

    response = test_client.post(
        "/api/chat",
        headers={
            "Authorization": "Bearer ignored",
            "traceparent": "00-abc-123-01",
            "x-extra-header": "blocked",
        },
        json={"mode": "customer_servicing", "content": "hello", "conversationId": "conv-1"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["message"]["role"] == "assistant"
    assert body["message"]["traceId"] == "resp-1"
    assert body["message"]["queriedSources"] == ["Fabric IQ", "Foundry IQ", "Work IQ"]
    assert body["message"]["groundingSources"] == ["Fabric IQ", "Foundry IQ", "Work IQ"]
    assert body["conversationId"] == "conv-1"
    assert body["quality"] == {"passed": True, "repaired": False, "citationCount": 1}
    assert foundry.calls[0]["forward_headers"] == {
        "x-client-demo-mode": "customer_servicing",
        "traceparent": "00-abc-123-01",
    }


def test_chat_history_shape_remains_available(client) -> None:
    test_client, foundry, _obo, _voice = client

    response = test_client.post(
        "/api/chat/history",
        headers={
            "Authorization": "Bearer ignored",
            "x-client-demo-mode": "service_discovery",
        },
        json={"messages": [{"role": "user", "content": "hello"}]},
    )

    assert response.status_code == 200
    assert response.json() == {"text": "reply from gpt-5.4-mini", "responseId": "resp-1"}
    assert foundry.calls[0]["forward_headers"] == {"x-client-demo-mode": "service_discovery"}


def test_chat_rejects_demo_mode_mismatch(client) -> None:
    test_client, _foundry, _obo, _voice = client

    response = test_client.post(
        "/api/chat",
        headers={
            "Authorization": "Bearer ignored",
            "x-client-demo-mode": "service_discovery",
        },
        json={"mode": "customer_servicing", "content": "hello"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_demo_mode"


def test_feedback_accepts_ui_shape(client) -> None:
    test_client, _foundry, _obo, _voice = client

    response = test_client.post(
        "/api/feedback",
        headers={"Authorization": "Bearer ignored"},
        json={"messageId": "resp-1", "sentiment": "negative"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "accepted",
        "messageId": "resp-1",
        "sentiment": "negative",
        "rating": 1,
    }


def test_role_enforcement_requires_reviewer_or_admin(settings: AppSettings) -> None:
    principal = AuthenticatedPrincipal(
        subject="subject-1",
        object_id="object-1",
        tenant_id="tenant-id",
        username="person@example.com",
        roles=frozenset({"BankServicing.Reader"}),
        scopes=frozenset({"BankServicing.Access"}),
        token="user-token",
    )
    app = create_app(
        settings,
        validator=FakeValidator(principal),
        obo_provider=FakeOboProvider(),
        foundry_client=FakeFoundryClient(),
        voice_handles=InMemoryVoiceHandleStore(ttl_seconds=settings.voice.handle_ttl_seconds),
        voice_client=FakeVoiceClient(),
        request_metrics=RequestMetrics(),
        conversations=InMemoryConversationStore(),
        review_store=InMemoryReviewStore(),
        quality_metrics=QualityMetricsSnapshot(),
    )

    with TestClient(app) as test_client:
        review_response = test_client.get(
            "/api/admin/content/reviews",
            headers={"Authorization": "Bearer ignored"},
        )
        admin_response = test_client.post(
            "/api/admin/evaluations/compare",
            headers={"Authorization": "Bearer ignored"},
            json={"prompt": "Synthetic prompt"},
        )

    assert review_response.status_code == 403
    assert admin_response.status_code == 403


def test_voice_handle_endpoint_requires_valid_client_context(client) -> None:
    test_client, _foundry, _obo, _voice = client

    response = test_client.post(
        "/api/voice/handles",
        headers={"Authorization": "Bearer ignored"},
        json={"clientContext": "desktop"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "voice_handle_invalid"
