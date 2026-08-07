from __future__ import annotations

import asyncio
from typing import Any
from urllib.parse import parse_qs

import httpx
import pytest

from bank_servicing_agent.agent_context import (
    reset_platform_user_id,
    set_platform_user_id,
)
from bank_servicing_agent.work_iq_mail import (
    AgenticUserTokenProvider,
    WorkIQAuthenticationUnavailableError,
    WorkIQMailServer,
    WorkIQMailTool,
)


def test_agentic_user_provider_uses_three_step_token_exchange() -> None:
    requests: list[dict[str, list[str]]] = []

    class AccessToken:
        token = "key-vault-token"

    class Credential:
        def get_token(self, scope: str) -> AccessToken:
            assert scope == "https://vault.azure.net/.default"
            return AccessToken()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            assert request.url.path == "/secrets/blueprint-secret"
            return httpx.Response(200, json={"value": "blueprint-client-secret"})
        requests.append(parse_qs(request.content.decode()))
        return httpx.Response(
            200,
            json={"access_token": f"token-{len(requests)}"},
        )

    provider = AgenticUserTokenProvider(
        tenant_id="tenant-id",
        blueprint_client_id="blueprint-id",
        instance_client_id="instance-id",
        blueprint_secret_vault_url="https://vault.example.test",
        blueprint_secret_name="blueprint-secret",
        credential=Credential(),
        http_client_factory=lambda: httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ),
    )

    token = asyncio.run(provider.get_token("agent-user-id", "audience/scope"))

    assert token == "token-3"
    assert requests[0]["fmi_path"] == ["instance-id"]
    assert requests[1]["client_assertion"] == ["token-1"]
    assert requests[2]["grant_type"] == ["user_fic"]
    assert requests[2]["user_id"] == ["agent-user-id"]


def test_mail_tool_uses_only_the_configured_agent_user() -> None:
    captured: dict[str, Any] = {}

    class TokenProvider:
        async def get_token(self, user_id: str, scope: str) -> str:
            captured["token"] = (user_id, scope)
            return "mail-token"

    async def runner(
        project_endpoint: str,
        model_deployment: str,
        credential: Any,
        server: WorkIQMailServer,
        token: str,
        question: str,
        require_send: bool,
    ) -> str:
        captured.update(
            project_endpoint=project_endpoint,
            model_deployment=model_deployment,
            server=server,
            delegated_token=token,
            question=question,
            require_send=require_send,
        )
        return "Work IQ confirmed the send."

    tool = WorkIQMailTool(
        project_endpoint="https://example.test/project",
        model_deployment="model",
        credential=object(),
        expected_agent_user_id="agent-user-id",
        token_provider=TokenProvider(),  # type: ignore[arg-type]
        server=WorkIQMailServer("https://example.test/mail", "mail-audience"),
        query_runner=runner,
    )
    context_token = set_platform_user_id("agent-user-id")
    try:
        result = asyncio.run(
            tool.send_email(
                "presenter@example.test",
                "Bank servicing verification",
                "This is a verification message.",
                "reviewer@example.test",
            )
        )
    finally:
        reset_platform_user_id(context_token)

    assert result == "Work IQ confirmed the send."
    assert captured["token"] == (
        "agent-user-id",
        "mail-audience/Tools.ListInvoke.All",
    )
    assert captured["require_send"] is True
    assert "Do not create a draft and do not retry" in captured["question"]
    assert "To recipients: presenter@example.test" in captured["question"]
    assert "Cc recipients: reviewer@example.test" in captured["question"]
    assert tool.as_read_tool().name == "read_agent_mailbox"
    assert tool.as_send_tool().name == "send_agent_email"


def test_mail_tool_rejects_obo_user_before_token_exchange() -> None:
    class TokenProvider:
        async def get_token(self, user_id: str, scope: str) -> str:
            raise AssertionError("Token exchange must not run for an OBO user")

    tool = WorkIQMailTool(
        project_endpoint="https://example.test/project",
        model_deployment="model",
        credential=object(),
        expected_agent_user_id="agent-user-id",
        token_provider=TokenProvider(),  # type: ignore[arg-type]
        server=WorkIQMailServer("https://example.test/mail", "mail-audience"),
    )
    context_token = set_platform_user_id("human-user-id")
    try:
        with pytest.raises(
            WorkIQAuthenticationUnavailableError,
            match="configured Agent 365 user",
        ):
            asyncio.run(tool.read_mailbox("Find my bank servicing email."))
    finally:
        reset_platform_user_id(context_token)
