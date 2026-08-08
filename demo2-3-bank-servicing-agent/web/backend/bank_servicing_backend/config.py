from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlencode
from urllib.parse import urlparse

from .errors import ConfigurationError


@dataclass(frozen=True, slots=True)
class EntraSettings:
    tenant_id: str
    audience: str
    client_id: str
    client_secret: str
    allowed_issuers: tuple[str, ...]
    required_scope: str | None
    authority: str
    clock_skew_seconds: int = 60


@dataclass(frozen=True, slots=True)
class RoleSettings:
    reviewer_roles: tuple[str, ...]
    admin_roles: tuple[str, ...]

    @property
    def reviewer_or_admin(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys((*self.reviewer_roles, *self.admin_roles)))


@dataclass(frozen=True, slots=True)
class FoundrySettings:
    project_endpoint: str
    agent_name: str
    model_name: str
    api_version: str
    scope: str = "https://ai.azure.com/.default"
    request_timeout_seconds: float = 90.0

    @property
    def responses_url(self) -> str:
        return f"{self.project_endpoint.rstrip('/')}/agents/{self.agent_name}/endpoint/protocols/openai/responses"


@dataclass(frozen=True, slots=True)
class VoiceSettings:
    endpoint: str
    api_version: str
    project_name: str
    agent_name: str
    voice_type: str
    voice_name: str
    avatar_enabled: bool
    avatar_character: str
    avatar_model: str
    avatar_customized: bool
    handle_ttl_seconds: int
    interim_response_enabled: bool = True
    interim_response_latency_threshold_ms: int = 800

    @property
    def websocket_url(self) -> str:
        query = urlencode(
            {
                "api-version": self.api_version,
                "agent-name": self.agent_name,
                "agent-project-name": self.project_name,
            }
        )
        return f"{self.endpoint.rstrip('/')}/voice-live/realtime?{query}"


@dataclass(frozen=True, slots=True)
class AppSettings:
    environment: str
    host: str
    port: int
    demo_modes: tuple[str, ...]
    entra: EntraSettings
    roles: RoleSettings
    foundry: FoundrySettings
    voice: VoiceSettings

    @classmethod
    def from_environment(cls) -> "AppSettings":
        environment = os.getenv("APP_ENVIRONMENT", "development").strip() or "development"
        host = os.getenv("APP_HOST", "0.0.0.0")
        port = int(os.getenv("APP_PORT", "8080"))
        demo_modes = _csv_env(
            "ALLOWED_DEMO_MODES",
            default=("customer_servicing", "service_discovery", "avatar_marketing"),
        )
        reviewer_roles = _csv_env("REVIEWER_ROLES")
        admin_roles = _csv_env("ADMIN_ROLES")
        if not reviewer_roles or not admin_roles:
            raise ConfigurationError("REVIEWER_ROLES and ADMIN_ROLES must both be configured")

        entra = EntraSettings(
            tenant_id=_required("ENTRA_TENANT_ID"),
            audience=_required("ENTRA_API_AUDIENCE"),
            client_id=_required("ENTRA_CLIENT_ID"),
            client_secret=_required("ENTRA_CLIENT_SECRET"),
            allowed_issuers=_csv_env(
                "ENTRA_ALLOWED_ISSUERS",
                default=(f"https://login.microsoftonline.com/{_required('ENTRA_TENANT_ID')}/v2.0",),
            ),
            required_scope=os.getenv("ENTRA_REQUIRED_SCOPE") or None,
            authority=os.getenv(
                "ENTRA_AUTHORITY",
                f"https://login.microsoftonline.com/{_required('ENTRA_TENANT_ID')}",
            ),
            clock_skew_seconds=int(os.getenv("ENTRA_CLOCK_SKEW_SECONDS", "60")),
        )

        foundry = FoundrySettings(
            project_endpoint=_required("FOUNDRY_PROJECT_ENDPOINT"),
            agent_name=os.getenv("FOUNDRY_AGENT_NAME", "bank-servicing-agent"),
            model_name=os.getenv("FOUNDRY_MODEL_NAME", "gpt-5.4-mini"),
            api_version=os.getenv("FOUNDRY_RESPONSES_API_VERSION", "2025-11-15-preview"),
            request_timeout_seconds=float(
                os.getenv("FOUNDRY_REQUEST_TIMEOUT_SECONDS", "360")
            ),
        )
        voice = VoiceSettings(
            endpoint=_required("VOICE_LIVE_ENDPOINT"),
            api_version=os.getenv("VOICE_LIVE_API_VERSION", "2026-04-10"),
            project_name=os.getenv("VOICE_LIVE_PROJECT_NAME", "4iq-foundry-project"),
            agent_name=os.getenv("VOICE_LIVE_AGENT_NAME", "bank-servicing-agent"),
            voice_type=os.getenv("VOICE_LIVE_VOICE_TYPE", "azure-standard"),
            voice_name=os.getenv(
                "VOICE_LIVE_VOICE",
                "en-US-AlloyTurboMultilingualNeural",
            ),
            avatar_enabled=_boolean_env("VOICE_LIVE_AVATAR_ENABLED", default=True),
            avatar_character=os.getenv("VOICE_LIVE_AVATAR_CHARACTER", "amara"),
            avatar_model=os.getenv("VOICE_LIVE_AVATAR_MODEL", "vasa-1"),
            avatar_customized=_boolean_env("VOICE_LIVE_AVATAR_CUSTOMIZED", default=False),
            handle_ttl_seconds=int(os.getenv("VOICE_HANDLE_TTL_SECONDS", "120")),
            interim_response_enabled=_boolean_env(
                "VOICE_LIVE_INTERIM_RESPONSE_ENABLED",
                default=True,
            ),
            interim_response_latency_threshold_ms=int(
                os.getenv("VOICE_LIVE_INTERIM_RESPONSE_LATENCY_MS", "800")
            ),
        )
        _validate_url(foundry.project_endpoint, require_path=True)
        _validate_url(voice.endpoint)
        if foundry.request_timeout_seconds <= 0:
            raise ConfigurationError("FOUNDRY_REQUEST_TIMEOUT_SECONDS must be greater than zero")
        if voice.handle_ttl_seconds <= 0:
            raise ConfigurationError("VOICE_HANDLE_TTL_SECONDS must be greater than zero")
        if voice.interim_response_latency_threshold_ms < 0:
            raise ConfigurationError(
                "VOICE_LIVE_INTERIM_RESPONSE_LATENCY_MS must be zero or greater"
            )
        return cls(
            environment=environment,
            host=host,
            port=port,
            demo_modes=demo_modes,
            entra=entra,
            roles=RoleSettings(reviewer_roles=reviewer_roles, admin_roles=admin_roles),
            foundry=foundry,
            voice=voice,
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


def _validate_url(value: str, *, require_path: bool = False) -> None:
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ConfigurationError(f"Expected an https URL, got: {value}")
    if require_path and not parsed.path:
        raise ConfigurationError(f"Expected URL path to be present: {value}")


def _boolean_env(name: str, *, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().casefold()
    if normalized in {"1", "true", "yes"}:
        return True
    if normalized in {"0", "false", "no"}:
        return False
    raise ConfigurationError(f"Expected {name} to be true or false")
