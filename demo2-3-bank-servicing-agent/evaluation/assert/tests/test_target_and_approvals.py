from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from bank_assert.correlation import CorrelationLedger, ScenarioCorrelation
from bank_assert.foundry import FoundryTargetConfig, _complete_approvals, invoke_hosted_agent
from bank_assert.identity import ValidatedIdentity
from bank_assert.target import Agent365Target, demo_mode_for_history


class FakeSidecar:
    async def acquire(self) -> ValidatedIdentity:
        return ValidatedIdentity(
            token="secret-token",
            claim_digest="digest",
            tenant_id="tenant",
            audience="audience",
            agent_user_id="agent-user",
            agent_identity_id="agent",
            parent_blueprint_id="parent",
            issued_at=1,
            expires_at=2,
        )


@pytest.mark.asyncio
async def test_target_does_not_duplicate_current_message(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, Any] = {}

    async def fake_invoke(**kwargs: Any) -> tuple[str, str, frozenset[str]]:
        captured.update(kwargs)
        return "answer", "response-1", frozenset()

    monkeypatch.setattr("bank_assert.target.invoke_hosted_agent", fake_invoke)
    target = Agent365Target.__new__(Agent365Target)
    target.sidecar = FakeSidecar()
    target.foundry = SimpleNamespace()
    target.correlation = ScenarioCorrelation("run-1", CorrelationLedger(tmp_path / "ledger.jsonl"))
    history = [
        {"role": "user", "content": "first"},
        {"role": "assistant", "content": "reply"},
        {"role": "user", "content": "current"},
    ]
    assert await target.chat("current", history) == "answer"
    assert captured["history"] == history[-40:]
    assert captured["history"].count({"role": "user", "content": "current"}) == 1
    assert captured["token"] == "secret-token"
    assert captured["demo_mode"] == "service_discovery"


@pytest.mark.asyncio
async def test_target_requires_message_to_match_history(tmp_path: Path) -> None:
    target = Agent365Target.__new__(Agent365Target)
    target.sidecar = FakeSidecar()
    target.foundry = SimpleNamespace()
    target.correlation = ScenarioCorrelation("run-1", CorrelationLedger(tmp_path / "ledger.jsonl"))
    with pytest.raises(ValueError, match="final user turn"):
        await target.chat("different", [{"role": "user", "content": "current"}])


@pytest.mark.asyncio
async def test_approval_continuation_preserves_identity_and_trace_headers() -> None:
    request = SimpleNamespace(type="mcp_approval_request", id="approval-1")
    first = SimpleNamespace(output=[request])
    final = SimpleNamespace(output=[SimpleNamespace(type="message")])
    calls: list[dict[str, Any]] = []

    async def create(**kwargs: Any) -> Any:
        calls.append(kwargs)
        return final

    client = SimpleNamespace(responses=SimpleNamespace(create=create))
    headers = {"traceparent": "00-abc-def-01", "baggage": "assert.run_id=run-1"}
    result = await _complete_approvals(
        client,
        model="model",
        history=[{"role": "user", "content": "test"}],
        response=first,
        headers=headers,
    )
    assert result is final
    assert calls[0]["extra_headers"] == headers
    assert calls[0]["input"][-1] == {
        "type": "mcp_approval_response",
        "approve": True,
        "approval_request_id": "approval-1",
    }


@pytest.mark.asyncio
async def test_foundry_invocation_authenticates_with_agent_user_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}
    response = SimpleNamespace(
        id="response-1",
        output=[
            SimpleNamespace(
                type="message",
                role="assistant",
                content=[SimpleNamespace(type="output_text", text="answer")],
            )
        ],
    )

    class FakeResponses:
        async def create(self, **kwargs: Any) -> Any:
            captured["request"] = kwargs
            return response

    class FakeClient:
        def __init__(self, **kwargs: Any) -> None:
            captured["client"] = kwargs
            self.responses = FakeResponses()

        async def close(self) -> None:
            captured["closed"] = True

    monkeypatch.setattr("bank_assert.foundry.AsyncOpenAI", FakeClient)
    text, response_id, sources = await invoke_hosted_agent(
        config=FoundryTargetConfig(
            endpoint="https://example.test/project",
            agent_name="bank-servicing-agent",
            agent_version="6",
            model="model",
            api_version="2025-05-15-preview",
        ),
        token="agent-user-token",
        history=[{"role": "user", "content": "hello"}],
        demo_mode="service_discovery",
        traceparent="00-abc-def-01",
        baggage="assert.run_id=run-1",
    )
    assert (text, response_id, sources) == ("answer", "response-1", frozenset())
    authorization = captured["client"]["default_headers"]["Authorization"]
    assert authorization.endswith("agent-user-token")
    assert "x-ms-user-identity" not in captured["client"]["default_headers"]
    request_headers = captured["request"]["extra_headers"]
    assert request_headers["Authorization"].endswith("agent-user-token")
    assert "x-ms-user-identity" not in request_headers
    assert request_headers["traceparent"] == "00-abc-def-01"
    assert request_headers["baggage"] == "assert.run_id=run-1"
    assert request_headers["x-client-demo-mode"] == "service_discovery"
    assert request_headers["x-ms-agent-version"] == "6"
    assert captured["closed"] is True


def test_demo_mode_routing_uses_current_user_turn() -> None:
    assert demo_mode_for_history([{"role": "user", "content": "Compare checking services"}]) == (
        "service_discovery"
    )
    history = [
        {"role": "user", "content": "Compare checking services"},
        {"role": "assistant", "content": "comparison"},
        {"role": "user", "content": "Now start the KYC application step"},
    ]
    assert demo_mode_for_history(history) == "customer_servicing"
    assert demo_mode_for_history(
        [{"role": "user", "content": "Check Work IQ for Outlook and Teams"}]
    ) == "customer_servicing"
