from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal, cast

import httpx

from .config import FoundrySettings
from .errors import UpstreamError

_ALLOWED_ROLES = {"user", "assistant", "system", "developer"}
_TRACE_HEADERS = {"traceparent", "tracestate", "baggage", "x-client-demo-mode"}


@dataclass(frozen=True, slots=True)
class Message:
    role: Literal["user", "assistant", "system", "developer"]
    content: str


@dataclass(frozen=True, slots=True)
class BridgeResponse:
    response_id: str
    text: str


class _BearerTokenAuth(httpx.Auth):
    def __init__(self, token: str) -> None:
        self._token = token

    def auth_flow(self, request: httpx.Request):
        request.headers["Authorization"] = "Bearer " + self._token
        yield request


class FoundryBridgeClient:
    def __init__(
        self,
        settings: FoundrySettings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        resolved_timeout = (
            settings.request_timeout_seconds
            if timeout_seconds is None
            else timeout_seconds
        )
        if resolved_timeout <= 0:
            raise ValueError("timeout_seconds must be greater than zero")
        self._settings = settings
        self._transport = transport
        self._timeout_seconds = resolved_timeout

    async def respond(
        self,
        *,
        bearer_token: str,
        messages: Sequence[Message],
        headers: dict[str, str] | None = None,
    ) -> BridgeResponse:
        payload = {
            "model": self._settings.model_name,
            "input": _history(messages),
        }
        safe_headers = {
            key: value
            for key, value in (headers or {}).items()
            if key.lower() in _TRACE_HEADERS
        }
        async with httpx.AsyncClient(
            timeout=self._timeout_seconds,
            transport=self._transport,
            trust_env=False,
            auth=_BearerTokenAuth(bearer_token),
        ) as client:
            response = await client.post(
                self._settings.responses_url,
                params={"api-version": self._settings.api_version},
                headers={
                    "Authorization": f"Bearer {bearer_token}",
                    "Content-Type": "application/json",
                    **safe_headers,
                },
                json=payload,
            )
        if response.status_code >= 400:
            raise UpstreamError(f"Foundry returned HTTP {response.status_code}")
        try:
            data = cast(dict[str, Any], response.json())
        except ValueError as exc:
            raise UpstreamError("Foundry returned invalid JSON") from exc
        text = _assistant_text(data)
        response_id = str(data.get("id") or "")
        if not text or not response_id:
            raise UpstreamError("Foundry returned an incomplete response")
        return BridgeResponse(response_id=response_id, text=text)


def _history(messages: Sequence[Message]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for message in messages:
        if message.role not in _ALLOWED_ROLES:
            raise ValueError(f"Unsupported role: {message.role}")
        result.append({"role": message.role, "content": message.content})
    return result


def _assistant_text(payload: dict[str, Any]) -> str:
    for item in payload.get("output", []):
        if item.get("type") != "message" or item.get("role") != "assistant":
            continue
        texts = [
            part.get("text", "")
            for part in item.get("content", [])
            if part.get("type") == "output_text"
        ]
        if texts:
            return "\n".join(texts)
    return ""
