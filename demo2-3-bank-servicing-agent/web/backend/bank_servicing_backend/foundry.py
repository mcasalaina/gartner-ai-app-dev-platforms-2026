from __future__ import annotations

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal, cast

import httpx

from .config import FoundrySettings
from .errors import UpstreamInvocationError

_ALLOWED_ROLES = {"user", "assistant", "system", "developer"}
_SOURCE_LINE = re.compile(r"(?im)^\s*Sources used:\s*(?P<sources>[^\r\n]+)\s*$")
_QUERY_LINE = re.compile(
    r"(?im)^\s*IQ services queried:\s*(?P<sources>[^\r\n]+)\s*$"
)
_GROUNDING_SOURCE_ALIASES = {
    "Fabric IQ": ("fabric iq", "fabric-iq-acmebank", "customer_finance"),
    "Foundry IQ": ("foundry iq", "bank-policy-foundryiq", "bank_policy"),
    "Work IQ": ("work iq", "workiq", "work_context"),
}


@dataclass(frozen=True, slots=True)
class Citation:
    id: str
    title: str
    url: str | None = None


@dataclass(frozen=True, slots=True)
class ChatMessage:
    role: Literal["user", "assistant", "system", "developer"]
    content: str


@dataclass(frozen=True, slots=True)
class FoundryResponse:
    response_id: str
    text: str
    citations: tuple[Citation, ...] = ()
    queried_sources: tuple[str, ...] = ()
    grounding_sources: tuple[str, ...] = ()
    model: str | None = None


class FoundryResponsesClient:
    def __init__(
        self,
        settings: FoundrySettings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        self._settings = settings
        self._transport = transport
        self._timeout_seconds = (
            settings.request_timeout_seconds if timeout_seconds is None else timeout_seconds
        )

    async def create_response(
        self,
        *,
        bearer_token: str,
        history: Sequence[ChatMessage],
        forward_headers: dict[str, str],
        model_override: str | None = None,
    ) -> FoundryResponse:
        model_name = model_override or self._settings.model_name
        headers = {
            "Authorization": f"Bearer {bearer_token}",
            "Content-Type": "application/json",
            **forward_headers,
        }
        payload: dict[str, Any] = {
            "model": model_name,
            "input": _response_history(history),
        }
        async with httpx.AsyncClient(
            timeout=self._timeout_seconds,
            transport=self._transport,
            trust_env=False,
        ) as client:
            response_data = await self._post(client, headers=headers, payload=payload)
            approvals = [
                item
                for item in response_data.get("output", [])
                if item.get("type") == "mcp_approval_request"
            ]
            if approvals:
                raise UpstreamInvocationError(
                    "Foundry requested explicit tool approval; use the authorized review workflow"
                )
        raw_text = _assistant_text(response_data)
        response_id = str(response_data.get("id") or "")
        if not raw_text or not response_id:
            raise UpstreamInvocationError("Foundry returned an incomplete response")
        queried_sources, grounding_sources = _extract_source_activity(response_data, raw_text)
        return FoundryResponse(
            response_id=response_id,
            text=_strip_source_activity(raw_text),
            citations=tuple(_extract_citations(response_data)),
            queried_sources=tuple(queried_sources),
            grounding_sources=tuple(grounding_sources),
            model=model_name,
        )

    async def _post(
        self,
        client: httpx.AsyncClient,
        *,
        headers: dict[str, str],
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        try:
            response = await client.post(
                self._settings.responses_url,
                params={"api-version": self._settings.api_version},
                headers=headers,
                json=payload,
            )
        except httpx.TimeoutException as exc:
            raise UpstreamInvocationError("Foundry invocation timed out") from exc
        if response.status_code >= 400:
            raise UpstreamInvocationError(
                f"Foundry invocation failed with HTTP {response.status_code}"
            )
        try:
            return cast(dict[str, Any], response.json())
        except ValueError as exc:
            raise UpstreamInvocationError("Foundry returned invalid JSON") from exc


def _response_history(history: Sequence[ChatMessage]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for item in history:
        if item.role not in _ALLOWED_ROLES:
            raise ValueError(f"Unsupported chat role: {item.role}")
        result.append({"role": item.role, "content": item.content})
    return result


def _assistant_text(response: dict[str, Any]) -> str:
    for item in response.get("output", []):
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


def _extract_citations(response: dict[str, Any]) -> list[Citation]:
    citations: list[Citation] = []
    for item in response.get("output", []):
        if item.get("type") != "message" or item.get("role") != "assistant":
            continue
        for part in item.get("content", []):
            annotations = part.get("annotations") or []
            for annotation in annotations:
                title = str(annotation.get("title") or annotation.get("text") or "Citation")
                citations.append(
                    Citation(
                        id=str(annotation.get("id") or len(citations) + 1),
                        title=title,
                        url=annotation.get("url"),
                    )
                )
    return citations


def _extract_source_activity(
    response: dict[str, Any],
    text: str,
) -> tuple[list[str], list[str]]:
    calls: list[dict[str, Any]] = []
    successful_calls: list[dict[str, Any]] = []
    for item in response.get("output", []):
        if not isinstance(item, dict) or item.get("type") != "mcp_call":
            continue
        calls.append(item)
        if item.get("error") or not item.get("output"):
            continue
        successful_calls.append(item)

    if calls:
        queried_haystack = json.dumps(calls, ensure_ascii=True).casefold()
        grounded_haystack = json.dumps(successful_calls, ensure_ascii=True).casefold()
        queried = [
            label
            for label, aliases in _GROUNDING_SOURCE_ALIASES.items()
            if any(alias in queried_haystack for alias in aliases)
        ]
        grounded = [
            label
            for label, aliases in _GROUNDING_SOURCE_ALIASES.items()
            if any(alias in grounded_haystack for alias in aliases)
        ]
        return queried, grounded

    queried_text = " ".join(match.group("sources") for match in _QUERY_LINE.finditer(text))
    grounded_text = " ".join(match.group("sources") for match in _SOURCE_LINE.finditer(text))
    queried = [
        label
        for label, aliases in _GROUNDING_SOURCE_ALIASES.items()
        if any(alias in queried_text.casefold() for alias in aliases)
    ]
    grounded = [
        label
        for label, aliases in _GROUNDING_SOURCE_ALIASES.items()
        if any(alias in grounded_text.casefold() for alias in aliases)
    ]
    return queried, grounded


def _strip_source_activity(text: str) -> str:
    return _QUERY_LINE.sub("", _SOURCE_LINE.sub("", text)).strip()
