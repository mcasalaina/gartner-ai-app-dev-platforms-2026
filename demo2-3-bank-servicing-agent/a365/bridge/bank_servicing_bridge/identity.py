from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import json
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol
from urllib.parse import quote, urlencode, urlsplit

import httpx
import jwt
from jwt import PyJWKClient

from .config import AgentUserSettings
from .errors import IdentityValidationError

_AGENT_USER_FACET = "13"
_AGENT_IDENTITY_FACET = "11"


class SigningKeyResolver(Protocol):
    def get_signing_key(self, token: str) -> Any: ...


class JwksResolver:
    def __init__(self, tenant_id: str) -> None:
        self._client = PyJWKClient(
            f"https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys",
            cache_keys=True,
        )

    def get_signing_key(self, token: str) -> Any:
        return self._client.get_signing_key_from_jwt(token).key


@dataclass(frozen=True, slots=True)
class ValidatedAgentUserToken:
    token: str = field(repr=False)
    tenant_id: str
    audience: str
    agent_user_id: str
    agent_identity_id: str
    parent_blueprint_id: str
    claim_digest: str
    expires_at: int


class AgentUserTokenValidator:
    def __init__(self, settings: AgentUserSettings, *, resolver: SigningKeyResolver | None = None) -> None:
        self._settings = settings
        self._resolver = resolver or JwksResolver(settings.tenant_id)

    async def validate(self, token: str) -> ValidatedAgentUserToken:
        try:
            unverified = jwt.decode(
                token,
                options={
                    "verify_signature": False,
                    "verify_aud": False,
                    "verify_exp": False,
                },
                algorithms=["RS256"],
            )
        except jwt.PyJWTError as exc:
            raise IdentityValidationError("The agent-user token is malformed") from exc

        if unverified.get("tid") != self._settings.tenant_id:
            raise IdentityValidationError("The agent-user token belongs to a different tenant")
        if unverified.get("iss") not in self._settings.allowed_issuers:
            raise IdentityValidationError("The agent-user token issuer is not allowed")

        try:
            key = await asyncio.to_thread(self._resolver.get_signing_key, token)
            claims: dict[str, Any] = jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                audience=self._settings.audience,
                options={"require": ["aud", "exp", "iss", "nbf", "oid", "tid"]},
                leeway=self._settings.clock_skew_seconds,
            )
        except jwt.PyJWTError as exc:
            raise IdentityValidationError("The agent-user token could not be verified") from exc

        _validate_claims(claims, self._settings)
        safe_claims = {
            key: claims.get(key)
            for key in (
                "aud",
                "azp",
                "appid",
                "exp",
                "idtyp",
                "nbf",
                "oid",
                "tid",
                "xms_act_fct",
                "xms_par_app_azp",
                "xms_sub_fct",
            )
        }
        digest = hashlib.sha256(
            json.dumps(safe_claims, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return ValidatedAgentUserToken(
            token=token,
            tenant_id=self._settings.tenant_id,
            audience=self._settings.audience,
            agent_user_id=self._settings.agent_user_id,
            agent_identity_id=self._settings.agent_identity_id,
            parent_blueprint_id=self._settings.parent_blueprint_id,
            claim_digest=digest,
            expires_at=int(claims["exp"]),
        )


class LoopbackTokenBroker:
    def __init__(
        self,
        settings: AgentUserSettings,
        validator: AgentUserTokenValidator,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep: Callable[[float], Any] = asyncio.sleep,
        timeout_seconds: float = 10.0,
        max_attempts: int = 3,
    ) -> None:
        self._settings = settings
        self._validator = validator
        self._transport = transport
        self._sleep = sleep
        self._timeout_seconds = timeout_seconds
        self._max_attempts = max_attempts
        if not _is_loopback(settings.sidecar_base_url):
            raise ValueError("The token broker must use an HTTP loopback URL")

    async def acquire(self) -> ValidatedAgentUserToken:
        query = urlencode(
            {
                "AgentIdentity": self._settings.agent_identity_id,
                "AgentUserId": self._settings.agent_user_id,
            }
        )
        url = (
            f"{self._settings.sidecar_base_url.rstrip('/')}/AuthorizationHeaderUnauthenticated/"
            f"{quote(self._settings.sidecar_service_name, safe='')}?{query}"
        )
        async with httpx.AsyncClient(
            timeout=self._timeout_seconds,
            transport=self._transport,
            trust_env=False,
        ) as client:
            response: httpx.Response | None = None
            for attempt in range(1, self._max_attempts + 1):
                try:
                    response = await client.get(url)
                except (httpx.NetworkError, httpx.TimeoutException) as exc:
                    if attempt == self._max_attempts:
                        raise IdentityValidationError("The loopback token broker is unavailable") from exc
                    await self._sleep(float(attempt))
                    continue
                if response.status_code < 500 and response.status_code != 429:
                    break
                if attempt == self._max_attempts:
                    raise IdentityValidationError(
                        f"The loopback token broker returned HTTP {response.status_code}"
                    )
                await self._sleep(float(attempt))
            if response is None or response.status_code != 200:
                status = response.status_code if response is not None else "unknown"
                raise IdentityValidationError(f"The loopback token broker returned HTTP {status}")
            try:
                authorization_header = response.json()["authorizationHeader"]
            except (KeyError, TypeError, ValueError) as exc:
                raise IdentityValidationError("The loopback token broker returned an invalid payload") from exc
        if not isinstance(authorization_header, str) or not authorization_header.startswith("Bearer "):
            raise IdentityValidationError("The loopback token broker did not return a bearer token")
        token = authorization_header.removeprefix("Bearer ").strip()
        if not token or " " in token:
            raise IdentityValidationError("The loopback token broker returned a malformed bearer token")
        return await self._validator.validate(token)


def _validate_claims(claims: Mapping[str, Any], settings: AgentUserSettings) -> None:
    failures: list[str] = []
    if claims.get("idtyp") != "user":
        failures.append("idtyp")
    if claims.get("oid") != settings.agent_user_id:
        failures.append("oid")
    if (claims.get("azp") or claims.get("appid")) != settings.agent_identity_id:
        failures.append("azp")
    if claims.get("xms_par_app_azp") != settings.parent_blueprint_id:
        failures.append("xms_par_app_azp")
    if _AGENT_USER_FACET not in _facet_values(claims.get("xms_sub_fct")):
        failures.append("xms_sub_fct")
    if _AGENT_IDENTITY_FACET not in _facet_values(claims.get("xms_act_fct")):
        failures.append("xms_act_fct")
    if failures:
        raise IdentityValidationError(
            f"The agent-user token failed required claim validation: {', '.join(failures)}"
        )
    now = int(time.time())
    if int(claims["nbf"]) > now + settings.clock_skew_seconds:
        raise IdentityValidationError("The agent-user token is not yet valid")
    if int(claims["exp"]) <= now - settings.clock_skew_seconds:
        raise IdentityValidationError("The agent-user token is expired")


def _facet_values(value: Any) -> set[str]:
    if isinstance(value, str):
        return {item for item in value.split() if item}
    if isinstance(value, list):
        return {str(item) for item in value}
    return set()


def _is_loopback(value: str) -> bool:
    parsed = urlsplit(value)
    if parsed.scheme != "http" or parsed.username or parsed.password:
        return False
    hostname = parsed.hostname
    if hostname == "localhost":
        return True
    if not hostname:
        return False
    try:
        return ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        return False
