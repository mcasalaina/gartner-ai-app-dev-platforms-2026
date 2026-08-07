from __future__ import annotations

import os
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote
from uuid import UUID

import httpx

from .config import AgentUserSettings
from .errors import ConfigurationError, UpstreamError

_CLIENT_ASSERTION_TYPE = "urn:ietf:params:oauth:client-assertion-type:jwt-bearer"
_TOKEN_EXCHANGE_SCOPE = "api://AzureADTokenExchange/.default"
_MSIP_LABEL_PROPERTY_ID = (
    "String {00020386-0000-0000-C000-000000000046} Name MSIP_Labels"
)

HttpClientFactory = Callable[[], AbstractAsyncContextManager[httpx.AsyncClient]]


@dataclass(frozen=True, slots=True)
class AgentGraphMailSettings:
    tenant_id: str
    blueprint_client_id: str
    instance_client_id: str
    agent_user_id: str
    blueprint_secret: str = field(repr=False)
    general_label_id: str
    general_label_name: str
    reply_cc_allowlist: tuple[str, ...]

    @classmethod
    def from_environment(
        cls,
        identity: AgentUserSettings,
    ) -> "AgentGraphMailSettings":
        label_id = _required("AGENT_EMAIL_GENERAL_LABEL_ID")
        try:
            UUID(label_id)
        except ValueError as exc:
            raise ConfigurationError(
                "AGENT_EMAIL_GENERAL_LABEL_ID must be a GUID"
            ) from exc
        allowlist = tuple(
            part.strip().casefold()
            for part in _required("AGENT_EMAIL_REPLY_CC_ALLOWLIST").split(",")
            if part.strip()
        )
        if not allowlist:
            raise ConfigurationError(
                "AGENT_EMAIL_REPLY_CC_ALLOWLIST must contain at least one address"
            )
        return cls(
            tenant_id=identity.tenant_id,
            blueprint_client_id=identity.parent_blueprint_id,
            instance_client_id=identity.agent_identity_id,
            agent_user_id=identity.agent_user_id,
            blueprint_secret=_required("CLIENT_SECRET"),
            general_label_id=label_id,
            general_label_name=_required("AGENT_EMAIL_GENERAL_LABEL_NAME"),
            reply_cc_allowlist=allowlist,
        )


class AgentGraphMailResponder:
    def __init__(
        self,
        settings: AgentGraphMailSettings,
        *,
        http_client_factory: HttpClientFactory | None = None,
    ) -> None:
        self.settings = settings
        self._http_client_factory = http_client_factory or (
            lambda: httpx.AsyncClient(timeout=30, trust_env=False)
        )
        self._handled_message_ids: set[str] = set()

    async def reply_to_message(
        self,
        *,
        message_id: str,
        html_body: str,
        cc_recipients: tuple[str, ...] = (),
    ) -> None:
        if not message_id.strip():
            raise ValueError("message_id must not be empty")
        if not html_body.strip():
            raise ValueError("html_body must not be empty")
        normalized_cc = tuple(address.strip().casefold() for address in cc_recipients)
        if any(address not in self.settings.reply_cc_allowlist for address in normalized_cc):
            raise ValueError("A requested Cc recipient is not allowlisted")
        if message_id in self._handled_message_ids:
            return

        async with self._http_client_factory() as client:
            graph_token = await self._graph_token(client)
            headers = {"Authorization": f"Bearer {graph_token}"}
            encoded_message_id = quote(message_id, safe="")
            draft_response = await client.post(
                "https://graph.microsoft.com/v1.0/me/messages/"
                f"{encoded_message_id}/createReply",
                headers=headers,
            )
            draft = _json_object(draft_response, "Microsoft Graph createReply")
            draft_id = draft.get("id")
            if not draft_response.is_success or not draft_id:
                raise UpstreamError("Microsoft Graph could not create the reply draft")

            label_value = self._label_value()
            update_response = await client.patch(
                "https://graph.microsoft.com/v1.0/me/messages/"
                f"{quote(str(draft_id), safe='')}",
                headers=headers,
                json={
                    "body": {"contentType": "HTML", "content": html_body},
                    "ccRecipients": [
                        {"emailAddress": {"address": address}}
                        for address in normalized_cc
                    ],
                    "singleValueExtendedProperties": [
                        {
                            "id": _MSIP_LABEL_PROPERTY_ID,
                            "value": label_value,
                        }
                    ],
                },
            )
            if not update_response.is_success:
                raise UpstreamError("Microsoft Graph could not update the reply draft")

            query = {
                "$select": "id,isDraft,ccRecipients",
                "$expand": (
                    "singleValueExtendedProperties"
                    f"($filter=id eq '{_MSIP_LABEL_PROPERTY_ID}')"
                ),
            }
            verify_response = await client.get(
                "https://graph.microsoft.com/v1.0/me/messages/"
                f"{quote(str(draft_id), safe='')}",
                headers=headers,
                params=query,
            )
            verified = _json_object(verify_response, "Microsoft Graph draft verification")
            verified_cc = tuple(
                str(item.get("emailAddress", {}).get("address", "")).casefold()
                for item in verified.get("ccRecipients", [])
            )
            verified_label = next(
                (
                    str(item.get("value", ""))
                    for item in verified.get("singleValueExtendedProperties", [])
                    if str(item.get("id", "")).casefold()
                    == _MSIP_LABEL_PROPERTY_ID.casefold()
                ),
                "",
            )
            if (
                not verify_response.is_success
                or not verified.get("isDraft")
                or verified_cc != normalized_cc
                or verified_label != label_value
            ):
                raise UpstreamError("Microsoft Graph reply draft verification failed")

            self._handled_message_ids.add(message_id)
            send_response = await client.post(
                "https://graph.microsoft.com/v1.0/me/messages/"
                f"{quote(str(draft_id), safe='')}/send",
                headers=headers,
            )
            if not send_response.is_success:
                raise UpstreamError("Microsoft Graph could not confirm the reply send")

    async def _graph_token(self, client: httpx.AsyncClient) -> str:
        blueprint_token = await self._exchange(
            client,
            {
                "client_id": self.settings.blueprint_client_id,
                "scope": _TOKEN_EXCHANGE_SCOPE,
                "grant_type": "client_credentials",
                "client_secret": self.settings.blueprint_secret,
                "fmi_path": self.settings.instance_client_id,
            },
        )
        instance_token = await self._exchange(
            client,
            {
                "client_id": self.settings.instance_client_id,
                "scope": _TOKEN_EXCHANGE_SCOPE,
                "grant_type": "client_credentials",
                "client_assertion_type": _CLIENT_ASSERTION_TYPE,
                "client_assertion": blueprint_token,
            },
        )
        return await self._exchange(
            client,
            {
                "client_id": self.settings.instance_client_id,
                "scope": "https://graph.microsoft.com/.default",
                "grant_type": "user_fic",
                "client_assertion_type": _CLIENT_ASSERTION_TYPE,
                "client_assertion": blueprint_token,
                "user_federated_identity_credential": instance_token,
                "user_id": self.settings.agent_user_id,
            },
        )

    async def _exchange(
        self,
        client: httpx.AsyncClient,
        data: dict[str, str],
    ) -> str:
        response = await client.post(
            "https://login.microsoftonline.com/"
            f"{self.settings.tenant_id}/oauth2/v2.0/token",
            data=data,
        )
        payload = _json_object(response, "Agent 365 token exchange")
        token = payload.get("access_token")
        if not response.is_success or not token:
            raise UpstreamError("Agent 365 token exchange failed")
        return str(token)

    def _label_value(self) -> str:
        prefix = f"MSIP_Label_{self.settings.general_label_id}_"
        set_date = datetime.now(UTC).isoformat(timespec="milliseconds").replace(
            "+00:00", "Z"
        )
        return ";".join(
            (
                f"{prefix}Enabled=True",
                f"{prefix}SiteId={self.settings.tenant_id}",
                f"{prefix}SetDate={set_date}",
                f"{prefix}Name={self.settings.general_label_name}",
                f"{prefix}ContentBits=1",
                f"{prefix}Method=Standard",
                "",
            )
        )


def _json_object(response: httpx.Response, operation: str) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError as exc:
        raise UpstreamError(f"{operation} returned an invalid response") from exc
    if not isinstance(payload, dict):
        raise UpstreamError(f"{operation} returned an invalid response")
    return payload


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ConfigurationError(f"Required environment variable is not set: {name}")
    return value
