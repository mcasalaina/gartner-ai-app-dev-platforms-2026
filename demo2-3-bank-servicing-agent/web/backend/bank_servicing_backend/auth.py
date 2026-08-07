from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Protocol

import jwt
from jwt import PyJWKClient

from .config import EntraSettings
from .errors import AuthenticationError, AuthorizationError


class SigningKeyResolver(Protocol):
    def get_signing_key(self, token: str) -> Any: ...


class JwksSigningKeyResolver:
    def __init__(self, tenant_id: str) -> None:
        self._client = PyJWKClient(
            f"https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys",
            cache_keys=True,
        )

    def get_signing_key(self, token: str) -> Any:
        return self._client.get_signing_key_from_jwt(token).key


@dataclass(frozen=True, slots=True)
class AuthenticatedPrincipal:
    subject: str
    object_id: str
    tenant_id: str
    username: str | None
    roles: frozenset[str]
    scopes: frozenset[str]
    token: str = field(repr=False)


class EntraJwtValidator:
    def __init__(
        self,
        settings: EntraSettings,
        *,
        resolver: SigningKeyResolver | None = None,
    ) -> None:
        self._settings = settings
        self._resolver = resolver or JwksSigningKeyResolver(settings.tenant_id)

    async def validate(self, token: str) -> AuthenticatedPrincipal:
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
            raise AuthenticationError("The access token is not a valid JWT") from exc

        if unverified.get("tid") != self._settings.tenant_id:
            raise AuthenticationError("The access token belongs to a different tenant")
        if unverified.get("iss") not in self._settings.allowed_issuers:
            raise AuthenticationError("The access token issuer is not allowed")
        if unverified.get("idtyp") == "app":
            raise AuthenticationError("Signed-in user requests require a delegated user token")

        try:
            signing_key = await asyncio.to_thread(self._resolver.get_signing_key, token)
            claims: dict[str, Any] = jwt.decode(
                token,
                signing_key,
                algorithms=["RS256"],
                audience=self._settings.audience,
                options={"require": ["aud", "exp", "iat", "iss", "sub", "tid", "oid"]},
                leeway=self._settings.clock_skew_seconds,
            )
        except jwt.PyJWTError as exc:
            raise AuthenticationError("The access token could not be verified") from exc

        scopes = _split_space_values(claims.get("scp"))
        if self._settings.required_scope and self._settings.required_scope not in scopes:
            raise AuthenticationError("The access token is missing the required delegated scope")

        roles = _claim_values(claims.get("roles"))
        return AuthenticatedPrincipal(
            subject=str(claims["sub"]),
            object_id=str(claims["oid"]),
            tenant_id=str(claims["tid"]),
            username=claims.get("preferred_username"),
            roles=frozenset(roles),
            scopes=frozenset(scopes),
            token=token,
        )


def require_any_role(principal: AuthenticatedPrincipal, allowed_roles: set[str] | frozenset[str]) -> None:
    if not principal.roles.intersection(allowed_roles):
        raise AuthorizationError("The signed-in user is missing a required app role")


def _split_space_values(value: Any) -> set[str]:
    if isinstance(value, str):
        return {item for item in value.split() if item}
    return set()


def _claim_values(value: Any) -> set[str]:
    if isinstance(value, str):
        return {value}
    if isinstance(value, list):
        return {str(item) for item in value}
    return set()
