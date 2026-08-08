from __future__ import annotations

from collections.abc import Iterable

import pytest
from fastapi.testclient import TestClient

from bank_servicing_backend.app import RequestMetrics, create_app
from bank_servicing_backend.auth import AuthenticatedPrincipal
from bank_servicing_backend.config import AppSettings, EntraSettings, FoundrySettings, RoleSettings, VoiceSettings
from bank_servicing_backend.foundry import Citation, FoundryResponse
from bank_servicing_backend.stores import InMemoryConversationStore, InMemoryReviewStore, QualityMetricsSnapshot
from bank_servicing_backend.voice import InMemoryVoiceHandleStore


class FakeValidator:
    def __init__(self, principal: AuthenticatedPrincipal) -> None:
        self.principal = principal

    async def validate(self, _token: str) -> AuthenticatedPrincipal:
        return self.principal


class FakeOboProvider:
    def __init__(self, token: str = "obo-token") -> None:
        self.token = token
        self.assertions: list[str] = []

    async def acquire(self, user_assertion: str, scope: str = "https://ai.azure.com/.default") -> str:
        self.assertions.append(f"{scope}:{user_assertion}")
        return self.token


class FakeFoundryClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def create_response(
        self,
        *,
        bearer_token: str,
        history,
        forward_headers: dict[str, str],
        model_override: str | None = None,
    ) -> FoundryResponse:
        self.calls.append(
            {
                "bearer_token": bearer_token,
                "history": list(history),
                "forward_headers": dict(forward_headers),
                "model_override": model_override,
            }
        )
        suffix = model_override or "gpt-5.4-mini"
        return FoundryResponse(
            response_id=f"resp-{len(self.calls)}",
            text=f"reply from {suffix}",
            citations=(Citation(id="c1", title="Synthetic source"),) if model_override is None else (),
            queried_sources=("Fabric IQ", "Foundry IQ", "Work IQ") if model_override is None else (),
            grounding_sources=("Fabric IQ", "Foundry IQ", "Work IQ") if model_override is None else (),
            model=suffix,
        )


class DummyUpstreamWebSocket:
    def __aiter__(self):
        return self

    async def __anext__(self):
        raise StopAsyncIteration

    async def send_str(self, _data: str) -> None:
        return None

    async def send_bytes(self, _data: bytes) -> None:
        return None


class DummyVoiceConnection:
    def __init__(self) -> None:
        self.websocket = DummyUpstreamWebSocket()
        self.closed = False

    async def close(self) -> None:
        self.closed = True


class FakeVoiceClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def open(self, ticket, *, obo_token: str) -> DummyVoiceConnection:
        self.calls.append({"ticket": ticket, "obo_token": obo_token})
        return DummyVoiceConnection()


@pytest.fixture
def settings() -> AppSettings:
    return AppSettings(
        environment="test",
        host="127.0.0.1",
        port=8080,
        demo_modes=("customer_servicing", "service_discovery", "avatar_marketing"),
        entra=EntraSettings(
            tenant_id="tenant-id",
            audience="api://bank-servicing",
            client_id="client-id",
            client_secret="secret",
            allowed_issuers=("https://login.microsoftonline.com/tenant-id/v2.0",),
            required_scope="BankServicing.Access",
            authority="https://login.microsoftonline.com/tenant-id",
        ),
        roles=RoleSettings(
            reviewer_roles=("BankServicing.ContentReviewer",),
            admin_roles=("BankServicing.Admin",),
        ),
        foundry=FoundrySettings(
            project_endpoint="https://example.services.ai.azure.com/api/projects/4iq-foundry-project",
            agent_name="bank-servicing-agent",
            model_name="gpt-5.4-mini",
            api_version="2025-11-15-preview",
        ),
        voice=VoiceSettings(
            endpoint="https://example.services.ai.azure.com",
            api_version="2026-04-10",
            project_name="4iq-foundry-project",
            agent_name="bank-servicing-agent",
            voice_type="azure-standard",
            voice_name="en-US-AlloyTurboMultilingualNeural",
            avatar_enabled=True,
            avatar_character="amara",
            avatar_model="vasa-1",
            avatar_customized=False,
            handle_ttl_seconds=120,
        ),
    )


@pytest.fixture
def principal() -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        subject="subject-1",
        object_id="object-1",
        tenant_id="tenant-id",
        username="person@example.com",
        roles=frozenset({"BankServicing.ContentReviewer", "BankServicing.Admin"}),
        scopes=frozenset({"BankServicing.Access"}),
        token="user-token",
    )


@pytest.fixture
def client(settings: AppSettings, principal: AuthenticatedPrincipal) -> Iterable[tuple[TestClient, FakeFoundryClient, FakeOboProvider, FakeVoiceClient]]:
    foundry = FakeFoundryClient()
    obo = FakeOboProvider()
    voice = FakeVoiceClient()
    app = create_app(
        settings,
        validator=FakeValidator(principal),
        obo_provider=obo,
        foundry_client=foundry,
        voice_handles=InMemoryVoiceHandleStore(ttl_seconds=settings.voice.handle_ttl_seconds),
        voice_client=voice,
        request_metrics=RequestMetrics(),
        conversations=InMemoryConversationStore(),
        review_store=InMemoryReviewStore(),
        quality_metrics=QualityMetricsSnapshot(),
    )
    with TestClient(app) as test_client:
        yield test_client, foundry, obo, voice
