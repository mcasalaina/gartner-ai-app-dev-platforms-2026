from __future__ import annotations

import json
from urllib.parse import parse_qs

import httpx
import pytest

from bank_servicing_bridge.graph_mail import (
    AgentGraphMailResponder,
    AgentGraphMailSettings,
)


@pytest.mark.asyncio
async def test_graph_reply_uses_agent_identity_cc_and_general_label() -> None:
    requests: list[httpx.Request] = []
    updated_draft: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.host == "login.microsoftonline.com":
            data = parse_qs(request.content.decode())
            if data["grant_type"] == ["user_fic"]:
                token = "graph-token"
            elif data["client_id"] == ["agent-identity-id"]:
                token = "instance-token"
            else:
                token = "blueprint-token"
            return httpx.Response(200, json={"access_token": token})
        if request.url.path.endswith("/createReply"):
            return httpx.Response(201, json={"id": "reply-draft-id"})
        if request.method == "PATCH":
            updated_draft.update(json.loads(request.content))
            return httpx.Response(200, json={"id": "reply-draft-id"})
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "id": "reply-draft-id",
                    "isDraft": True,
                    "ccRecipients": updated_draft["ccRecipients"],
                    "singleValueExtendedProperties": updated_draft[
                        "singleValueExtendedProperties"
                    ],
                },
            )
        if request.url.path.endswith("/send"):
            return httpx.Response(202)
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    transport = httpx.MockTransport(handler)
    responder = AgentGraphMailResponder(
        AgentGraphMailSettings(
            tenant_id="tenant-id",
            blueprint_client_id="blueprint-id",
            instance_client_id="agent-identity-id",
            agent_user_id="agent-user-id",
            blueprint_secret="blueprint-secret",
            general_label_id="defa4170-0d19-0005-0004-bc88714345d2",
            general_label_name="All Employees (unrestricted)",
            reply_cc_allowlist=("marco@example.com",),
        ),
        http_client_factory=lambda: httpx.AsyncClient(transport=transport),
    )

    await responder.reply_to_message(
        message_id="message/id",
        html_body="<p>Reply body</p>",
        cc_recipients=("marco@example.com",),
    )

    assert updated_draft["ccRecipients"] == [
        {"emailAddress": {"address": "marco@example.com"}}
    ]
    properties = updated_draft["singleValueExtendedProperties"]
    assert isinstance(properties, list)
    assert properties[0]["id"].endswith("Name MSIP_Labels")
    assert "_Name=All Employees (unrestricted);" in properties[0]["value"]
    token_requests = [
        parse_qs(request.content.decode())
        for request in requests
        if request.url.host == "login.microsoftonline.com"
    ]
    assert token_requests[-1]["grant_type"] == ["user_fic"]
    assert token_requests[-1]["user_id"] == ["agent-user-id"]


@pytest.mark.asyncio
async def test_graph_reply_rejects_unapproved_cc() -> None:
    responder = AgentGraphMailResponder(
        AgentGraphMailSettings(
            tenant_id="tenant-id",
            blueprint_client_id="blueprint-id",
            instance_client_id="agent-identity-id",
            agent_user_id="agent-user-id",
            blueprint_secret="blueprint-secret",
            general_label_id="defa4170-0d19-0005-0004-bc88714345d2",
            general_label_name="All Employees (unrestricted)",
            reply_cc_allowlist=("marco@example.com",),
        )
    )

    with pytest.raises(ValueError, match="not allowlisted"):
        await responder.reply_to_message(
            message_id="message-id",
            html_body="<p>Reply body</p>",
            cc_recipients=("other@example.com",),
        )
