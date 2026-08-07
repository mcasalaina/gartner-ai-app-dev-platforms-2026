from __future__ import annotations

import httpx
import pytest

from bank_servicing_bridge.agent import BankServicingAgent
from bank_servicing_bridge.errors import UpstreamError
from bank_servicing_bridge.foundry import BridgeResponse


def test_bridge_uses_agent_user_token_and_preserves_history(client) -> None:
    test_client, broker, foundry = client

    first = test_client.post(
        "/api/respond",
        headers={"traceparent": "00-abc-123-01", "x-client-demo-mode": "customer_servicing"},
        json={"conversationId": "conv-1", "message": "hello"},
    )
    second = test_client.post(
        "/api/respond",
        json={"conversationId": "conv-1", "message": "follow up"},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert broker.calls == 2
    assert foundry.calls[0]["bearer_token"] == "agent-user-token"
    assert len(foundry.calls[1]["messages"]) == 3
    assert foundry.calls[0]["headers"] == {
        "traceparent": "00-abc-123-01",
        "x-client-demo-mode": "customer_servicing",
    }


def test_bridge_rejects_legacy_demo_mode_header(client) -> None:
    test_client, _broker, _foundry = client

    response = test_client.post(
        "/api/respond",
        headers={"x-client-demo-mode": "customerServicing"},
        json={"conversationId": "conv-1", "message": "hello"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_demo_mode"


@pytest.mark.asyncio
async def test_failed_foundry_turn_is_removed_from_conversation_history() -> None:
    class Broker:
        async def acquire(self):
            class Token:
                token = "agent-user-token"

            return Token()

    class FailsOnceFoundry:
        def __init__(self) -> None:
            self.calls = []

        async def respond(self, *, bearer_token, messages, headers=None):
            self.calls.append(list(messages))
            if len(self.calls) == 1:
                request = httpx.Request("POST", "https://example.test/responses")
                raise httpx.ReadTimeout("timed out", request=request)
            return BridgeResponse(response_id="response-2", text="recovered")

    foundry = FailsOnceFoundry()
    agent = BankServicingAgent(token_broker=Broker(), foundry_client=foundry)

    with pytest.raises(UpstreamError, match="timed out"):
        await agent.respond("first turn", conversation_id="conversation-1")
    response = await agent.respond("second turn", conversation_id="conversation-1")

    assert response.text == "recovered"
    assert [message.content for message in foundry.calls[1]] == ["second turn"]
