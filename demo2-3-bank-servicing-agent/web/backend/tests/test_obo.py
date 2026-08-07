from __future__ import annotations

import pytest

from bank_servicing_backend.config import EntraSettings
from bank_servicing_backend.errors import OboExchangeError
from bank_servicing_backend.obo import OboTokenProvider


class FakeMsalApp:
    def __init__(self, result):
        self.result = result
        self.calls: list[tuple[str, tuple[str, ...]]] = []

    def acquire_token_on_behalf_of(self, user_assertion: str, scopes: list[str]):
        self.calls.append((user_assertion, tuple(scopes)))
        return self.result


@pytest.mark.asyncio
async def test_obo_provider_uses_user_assertion() -> None:
    app = FakeMsalApp({"access_token": "obo-token"})
    provider = OboTokenProvider(
        EntraSettings(
            tenant_id="tenant-id",
            audience="api://bank-servicing",
            client_id="client-id",
            client_secret="secret",
            allowed_issuers=("https://login.microsoftonline.com/tenant-id/v2.0",),
            required_scope=None,
            authority="https://login.microsoftonline.com/tenant-id",
        ),
        app_factory=lambda: app,
    )

    token = await provider.acquire("user-token")

    assert token == "obo-token"
    assert app.calls == [("user-token", ("https://ai.azure.com/.default",))]


@pytest.mark.asyncio
async def test_obo_provider_raises_on_exchange_failure() -> None:
    provider = OboTokenProvider(
        EntraSettings(
            tenant_id="tenant-id",
            audience="api://bank-servicing",
            client_id="client-id",
            client_secret="secret",
            allowed_issuers=("https://login.microsoftonline.com/tenant-id/v2.0",),
            required_scope=None,
            authority="https://login.microsoftonline.com/tenant-id",
        ),
        app_factory=lambda: FakeMsalApp({"error": "invalid_grant", "error_codes": [12345]}),
    )

    with pytest.raises(OboExchangeError):
        await provider.acquire("user-token")
