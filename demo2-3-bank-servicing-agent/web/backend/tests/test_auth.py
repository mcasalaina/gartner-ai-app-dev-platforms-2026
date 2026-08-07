from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

from bank_servicing_backend.auth import EntraJwtValidator
from bank_servicing_backend.config import EntraSettings
from bank_servicing_backend.errors import AuthenticationError


class StaticResolver:
    def __init__(self, key) -> None:
        self.key = key

    def get_signing_key(self, _token: str):
        return self.key


@pytest.fixture
def rsa_keys():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    return private_key, public_key


@pytest.fixture
def entra_settings() -> EntraSettings:
    return EntraSettings(
        tenant_id="tenant-id",
        audience="api://bank-servicing",
        client_id="client-id",
        client_secret="secret",
        allowed_issuers=("https://login.microsoftonline.com/tenant-id/v2.0",),
        required_scope="BankServicing.Access",
        authority="https://login.microsoftonline.com/tenant-id",
    )


def _token(private_key, *, audience: str = "api://bank-servicing", issuer: str = "https://login.microsoftonline.com/tenant-id/v2.0", exp_minutes: int = 5, tenant_id: str = "tenant-id", scopes: str = "BankServicing.Access", roles: list[str] | None = None) -> str:
    now = datetime.now(tz=UTC)
    return jwt.encode(
        {
            "aud": audience,
            "iss": issuer,
            "tid": tenant_id,
            "sub": "sub-1",
            "oid": "oid-1",
            "iat": int(now.timestamp()),
            "nbf": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=exp_minutes)).timestamp()),
            "scp": scopes,
            "roles": roles or ["BankServicing.Admin"],
        },
        private_key,
        algorithm="RS256",
    )


@pytest.mark.asyncio
async def test_validator_accepts_signed_user_token(entra_settings: EntraSettings, rsa_keys) -> None:
    private_key, public_key = rsa_keys
    validator = EntraJwtValidator(entra_settings, resolver=StaticResolver(public_key))

    principal = await validator.validate(_token(private_key))

    assert principal.object_id == "oid-1"
    assert "BankServicing.Admin" in principal.roles


@pytest.mark.asyncio
async def test_validator_rejects_wrong_audience(entra_settings: EntraSettings, rsa_keys) -> None:
    private_key, public_key = rsa_keys
    validator = EntraJwtValidator(entra_settings, resolver=StaticResolver(public_key))

    with pytest.raises(AuthenticationError):
        await validator.validate(_token(private_key, audience="api://other"))


@pytest.mark.asyncio
async def test_validator_rejects_wrong_issuer(entra_settings: EntraSettings, rsa_keys) -> None:
    private_key, public_key = rsa_keys
    validator = EntraJwtValidator(entra_settings, resolver=StaticResolver(public_key))

    with pytest.raises(AuthenticationError):
        await validator.validate(_token(private_key, issuer="https://issuer.example/v2.0"))


@pytest.mark.asyncio
async def test_validator_rejects_expired_token(entra_settings: EntraSettings, rsa_keys) -> None:
    private_key, public_key = rsa_keys
    validator = EntraJwtValidator(entra_settings, resolver=StaticResolver(public_key))

    with pytest.raises(AuthenticationError):
        await validator.validate(_token(private_key, exp_minutes=-5))
