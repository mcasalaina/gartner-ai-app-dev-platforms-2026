from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from bank_servicing_bridge.config import AgentUserSettings
from bank_servicing_bridge.errors import IdentityValidationError
from bank_servicing_bridge.identity import AgentUserTokenValidator


class StaticResolver:
    def __init__(self, key) -> None:
        self.key = key

    def get_signing_key(self, _token: str):
        return self.key


@pytest.fixture
def settings() -> AgentUserSettings:
    return AgentUserSettings(
        tenant_id="tenant-id",
        allowed_issuers=(
            "https://login.microsoftonline.com/tenant-id/v2.0",
            "https://sts.windows.net/tenant-id/",
        ),
        audience="api://agent-365-sidecar",
        agent_user_id="agent-user-id",
        agent_identity_id="agent-identity-id",
        parent_blueprint_id="parent-blueprint-id",
        clock_skew_seconds=60,
        sidecar_service_name="BankServicingAgent",
        sidecar_base_url="http://127.0.0.1:8081",
    )


def _token(private_key, *, issuer="https://login.microsoftonline.com/tenant-id/v2.0", oid="agent-user-id", azp="agent-identity-id", parent="parent-blueprint-id") -> str:
    now = datetime.now(tz=UTC)
    return jwt.encode(
        {
            "aud": "api://agent-365-sidecar",
            "iss": issuer,
            "tid": "tenant-id",
            "oid": oid,
            "azp": azp,
            "idtyp": "user",
            "nbf": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=5)).timestamp()),
            "xms_sub_fct": ["1", "13"],
            "xms_act_fct": ["11"],
            "xms_par_app_azp": parent,
        },
        private_key,
        algorithm="RS256",
    )


@pytest.mark.asyncio
async def test_agent_user_validator_accepts_expected_claims(settings: AgentUserSettings) -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    validator = AgentUserTokenValidator(settings, resolver=StaticResolver(private_key.public_key()))

    validated = await validator.validate(_token(private_key))

    assert validated.agent_user_id == "agent-user-id"
    assert validated.claim_digest


@pytest.mark.asyncio
async def test_agent_user_validator_fails_closed_on_claim_mismatch(settings: AgentUserSettings) -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    validator = AgentUserTokenValidator(settings, resolver=StaticResolver(private_key.public_key()))

    with pytest.raises(IdentityValidationError):
        await validator.validate(_token(private_key, oid="someone-else"))
