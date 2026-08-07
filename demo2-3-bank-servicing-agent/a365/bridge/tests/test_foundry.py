from __future__ import annotations

import httpx
import pytest

from bank_servicing_bridge.config import FoundrySettings
from bank_servicing_bridge.foundry import FoundryBridgeClient, Message


@pytest.mark.asyncio
async def test_foundry_client_routes_only_the_agent_user_bearer_token() -> None:
    captured: dict[str, str | None] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["authorization"] = request.headers.get("Authorization")
        captured["caller"] = request.headers.get("x-ms-user-identity")
        return httpx.Response(
            200,
            json={
                "id": "response-1",
                "output": [
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": "ok"}],
                    }
                ],
            },
        )

    client = FoundryBridgeClient(
        FoundrySettings(
            project_endpoint="https://example.test/api/projects/project",
            agent_name="bank-servicing-agent",
            model_name="gpt-5.4-mini",
            api_version="v1",
        ),
        transport=httpx.MockTransport(handler),
    )

    await client.respond(
        bearer_token="synthetic-agent-user-token",
        messages=[Message(role="user", content="synthetic fee dispute")],
        headers={"Authorization": "Bearer caller-token", "traceparent": "trace"},
    )

    assert captured["authorization"] == "Bearer synthetic-agent-user-token"
    assert captured["caller"] is None


def test_foundry_client_uses_configured_timeout() -> None:
    client = FoundryBridgeClient(
        FoundrySettings(
            project_endpoint="https://example.test/api/projects/project",
            agent_name="bank-servicing-agent",
            model_name="gpt-5.4-mini",
            api_version="v1",
            request_timeout_seconds=360,
        )
    )

    assert client._timeout_seconds == 360
