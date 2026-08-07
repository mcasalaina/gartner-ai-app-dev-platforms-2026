from __future__ import annotations

import httpx
import pytest

from bank_servicing_backend.config import FoundrySettings
from bank_servicing_backend.errors import UpstreamInvocationError
from bank_servicing_backend.foundry import ChatMessage, FoundryResponsesClient


@pytest.mark.asyncio
async def test_foundry_client_never_auto_approves_tool_requests() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "id": "response-1",
                "output": [
                    {
                        "type": "mcp_approval_request",
                        "id": "approval-1",
                    }
                ],
            },
        )

    client = FoundryResponsesClient(
        FoundrySettings(
            project_endpoint="https://example.services.ai.azure.com/api/projects/project",
            agent_name="bank-servicing-agent",
            model_name="gpt-5.4-mini",
            api_version="2025-11-15-preview",
        ),
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(UpstreamInvocationError, match="explicit tool approval"):
        await client.create_response(
            bearer_token="token",
            history=[ChatMessage(role="user", content="Publish this draft")],
            forward_headers={"x-client-demo-mode": "service_discovery"},
        )


@pytest.mark.asyncio
async def test_foundry_client_surfaces_timeout_as_upstream_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    client = FoundryResponsesClient(
        FoundrySettings(
            project_endpoint="https://example.services.ai.azure.com/api/projects/project",
            agent_name="bank-servicing-agent",
            model_name="gpt-5.4-mini",
            api_version="2025-11-15-preview",
        ),
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(UpstreamInvocationError, match="timed out"):
        await client.create_response(
            bearer_token="token",
            history=[ChatMessage(role="user", content="Compare checking and savings.")],
            forward_headers={"x-client-demo-mode": "service_discovery"},
        )


@pytest.mark.asyncio
async def test_foundry_client_reports_tool_sources_and_strips_source_marker() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "id": "response-1",
                "output": [
                    {
                        "type": "mcp_call",
                        "server_label": "fabric-iq-acmebank",
                        "name": "customer_finance",
                        "output": "Customer results",
                    },
                    {
                        "type": "mcp_call",
                        "server_label": "bank-policy-foundryiq",
                        "name": "bank_policy",
                        "output": "Policy results",
                    },
                    {
                        "type": "mcp_call",
                        "server_label": "workiq",
                        "name": "work_context",
                        "error": "Upstream unavailable",
                    },
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [
                            {
                                "type": "output_text",
                                "text": (
                                    "Grounded answer [S1].\n\n"
                                    "IQ services queried: Fabric IQ, Foundry IQ, Work IQ\n"
                                    "Sources used: Fabric IQ, Foundry IQ"
                                ),
                            }
                        ],
                    },
                ],
            },
        )

    client = FoundryResponsesClient(
        FoundrySettings(
            project_endpoint="https://example.services.ai.azure.com/api/projects/project",
            agent_name="bank-servicing-agent",
            model_name="gpt-5.4-mini",
            api_version="2025-11-15-preview",
        ),
        transport=httpx.MockTransport(handler),
    )

    result = await client.create_response(
        bearer_token="token",
        history=[ChatMessage(role="user", content="Use all three grounded sources.")],
        forward_headers={"x-client-demo-mode": "service_discovery"},
    )

    assert result.text == "Grounded answer [S1]."
    assert result.queried_sources == ("Fabric IQ", "Foundry IQ", "Work IQ")
    assert result.grounding_sources == ("Fabric IQ", "Foundry IQ")


@pytest.mark.asyncio
async def test_foundry_client_does_not_trust_source_citations_without_activity_footer() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "id": "response-2",
                "output": [
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [
                            {
                                "type": "output_text",
                                "text": (
                                    "Fabric result [F1]. Policy result [P1]. "
                                    "Work lookup was unavailable [W1]."
                                ),
                            }
                        ],
                    }
                ],
            },
        )

    client = FoundryResponsesClient(
        FoundrySettings(
            project_endpoint="https://example.services.ai.azure.com/api/projects/project",
            agent_name="bank-servicing-agent",
            model_name="gpt-5.4-mini",
            api_version="2025-11-15-preview",
        ),
        transport=httpx.MockTransport(handler),
    )

    result = await client.create_response(
        bearer_token="token",
        history=[ChatMessage(role="user", content="Use all three grounded sources.")],
        forward_headers={"x-client-demo-mode": "service_discovery"},
    )

    assert result.text == (
        "Fabric result [F1]. Policy result [P1]. Work lookup was unavailable [W1]."
    )
    assert result.queried_sources == ()
    assert result.grounding_sources == ()
