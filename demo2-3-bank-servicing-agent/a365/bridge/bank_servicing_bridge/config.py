from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlparse

from .errors import ConfigurationError


@dataclass(frozen=True, slots=True)
class AgentUserSettings:
    tenant_id: str
    allowed_issuers: tuple[str, ...]
    audience: str
    agent_user_id: str
    agent_identity_id: str
    parent_blueprint_id: str
    clock_skew_seconds: int
    sidecar_service_name: str
    sidecar_base_url: str


@dataclass(frozen=True, slots=True)
class FoundrySettings:
    project_endpoint: str
    agent_name: str
    model_name: str
    api_version: str
    request_timeout_seconds: float = 360.0

    @property
    def responses_url(self) -> str:
        return f"{self.project_endpoint.rstrip('/')}/agents/{self.agent_name}/endpoint/protocols/openai/responses"


@dataclass(frozen=True, slots=True)
class BridgeSettings:
    environment: str
    host: str
    port: int
    identity: AgentUserSettings
    foundry: FoundrySettings

    @classmethod
    def from_environment(cls) -> "BridgeSettings":
        identity = AgentUserSettings(
            tenant_id=_required("ENTRA_TENANT_ID"),
            allowed_issuers=_csv_env(
                "ENTRA_ALLOWED_ISSUERS",
                default=(f"https://login.microsoftonline.com/{_required('ENTRA_TENANT_ID')}/v2.0",),
            ),
            audience=_required("AGENT_USER_AUDIENCE"),
            agent_user_id=_required("AGENT_USER_ID"),
            agent_identity_id=_required("AGENT_IDENTITY_ID"),
            parent_blueprint_id=_required("PARENT_BLUEPRINT_ID"),
            clock_skew_seconds=int(os.getenv("AGENT_USER_CLOCK_SKEW_SECONDS", "60")),
            sidecar_service_name=os.getenv("SIDE_CAR_SERVICE_NAME", "BankServicingAgent"),
            sidecar_base_url=os.getenv("SIDE_CAR_BASE_URL", "http://127.0.0.1:8081"),
        )
        foundry = FoundrySettings(
            project_endpoint=_required("FOUNDRY_PROJECT_ENDPOINT"),
            agent_name=os.getenv("FOUNDRY_AGENT_NAME", "bank-servicing-agent"),
            model_name=os.getenv("FOUNDRY_MODEL_NAME", "gpt-5.4-mini"),
            api_version=os.getenv("FOUNDRY_RESPONSES_API_VERSION", "v1"),
            request_timeout_seconds=float(
                os.getenv("FOUNDRY_REQUEST_TIMEOUT_SECONDS", "360")
            ),
        )
        _validate_https(foundry.project_endpoint)
        _validate_loopback_http(identity.sidecar_base_url)
        if foundry.request_timeout_seconds <= 0:
            raise ConfigurationError(
                "FOUNDRY_REQUEST_TIMEOUT_SECONDS must be greater than zero"
            )
        return cls(
            environment=os.getenv("BRIDGE_ENVIRONMENT", "development"),
            host=os.getenv("BRIDGE_HOST", "0.0.0.0"),
            port=int(os.getenv("PORT", os.getenv("BRIDGE_PORT", "8080"))),
            identity=identity,
            foundry=foundry,
        )


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ConfigurationError(f"Required environment variable is not set: {name}")
    return value


def _csv_env(name: str, default: tuple[str, ...] = ()) -> tuple[str, ...]:
    value = os.getenv(name)
    if value is None:
        return default
    parts = tuple(part.strip() for part in value.split(",") if part.strip())
    return parts or default


def _validate_https(value: str) -> None:
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ConfigurationError(f"Expected an https URL, got: {value}")


def _validate_loopback_http(value: str) -> None:
    parsed = urlparse(value)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}:
        raise ConfigurationError("SIDE_CAR_BASE_URL must use http loopback")
