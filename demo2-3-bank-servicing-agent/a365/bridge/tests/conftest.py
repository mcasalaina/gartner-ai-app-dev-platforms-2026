from __future__ import annotations

from collections.abc import Iterable

import pytest
from fastapi.testclient import TestClient

from bank_servicing_bridge.agent import BankServicingAgent
from bank_servicing_bridge.app import create_app
from bank_servicing_bridge.config import AgentUserSettings, BridgeSettings, FoundrySettings
from bank_servicing_bridge.foundry import BridgeResponse


class FakeBroker:
    def __init__(self, token: str = "agent-user-token") -> None:
        self.token = token
        self.calls = 0

    async def acquire(self):
        self.calls += 1
        class Token:
            def __init__(self, token: str) -> None:
                self.token = token
        return Token(self.token)


class FakeFoundryClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def respond(self, *, bearer_token: str, messages, headers=None) -> BridgeResponse:
        self.calls.append(
            {
                "bearer_token": bearer_token,
                "messages": list(messages),
                "headers": dict(headers or {}),
            }
        )
        return BridgeResponse(response_id="bridge-resp-1", text="bridge hello")


@pytest.fixture
def settings() -> BridgeSettings:
    return BridgeSettings(
        environment="test",
        host="127.0.0.1",
        port=8090,
        identity=AgentUserSettings(
            tenant_id="tenant-id",
            allowed_issuers=(
                "https://login.microsoftonline.com/tenant-id/v2.0",
                "https://sts.windows.net/tenant-id/",
            ),
            audience="api://agent-365-sidecar",
            agent_user_id="agent-user-id",
            agent_identity_id="agent-identity-id",
            parent_blueprint_id="parent-blueprint-id",
            clock_skew_seconds=60,
            sidecar_service_name="BankServicingAgent",
            sidecar_base_url="http://127.0.0.1:8081",
        ),
        foundry=FoundrySettings(
            project_endpoint="https://example.services.ai.azure.com/api/projects/4iq-foundry-project",
            agent_name="bank-servicing-agent",
            model_name="gpt-5.4-mini",
            api_version="2025-11-15-preview",
        ),
    )


@pytest.fixture
def client(settings: BridgeSettings) -> Iterable[tuple[TestClient, FakeBroker, FakeFoundryClient]]:
    broker = FakeBroker()
    foundry = FakeFoundryClient()
    app = create_app(
        settings,
        agent=BankServicingAgent(token_broker=broker, foundry_client=foundry),
    )
    with TestClient(app) as test_client:
        yield test_client, broker, foundry
