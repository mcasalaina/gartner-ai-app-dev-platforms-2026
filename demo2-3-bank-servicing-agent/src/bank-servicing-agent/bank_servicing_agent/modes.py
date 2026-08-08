from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum


class DemoMode(StrEnum):
    SERVICE_DISCOVERY = "service_discovery"
    CUSTOMER_SERVICING = "customer_servicing"
    AVATAR_MARKETING = "avatar_marketing"


class AvatarTone(StrEnum):
    PROFESSIONAL = "professional"
    WARM = "warm"
    ENERGETIC = "energetic"


class DemoModeError(ValueError):
    """Raised when the trusted operating mode is missing or invalid."""



def resolve_demo_mode(client_headers: Mapping[str, str] | None) -> DemoMode:
    if not client_headers:
        raise DemoModeError(
            "Missing required trusted operating mode. Supported values are "
            "service_discovery, customer_servicing, and avatar_marketing."
        )
    value = client_headers.get("x-client-demo-mode")
    if value is None or not value.strip():
        raise DemoModeError(
            "Missing required trusted operating mode. Supported values are "
            "service_discovery, customer_servicing, and avatar_marketing."
        )
    normalized = value.strip().lower()
    try:
        return DemoMode(normalized)
    except ValueError as exc:
        raise DemoModeError(
            f"Unsupported trusted operating mode '{value}'. Supported values are "
            "service_discovery, customer_servicing, and avatar_marketing."
        ) from exc


def resolve_avatar_tone(
    client_headers: Mapping[str, str] | None,
    mode: DemoMode,
) -> AvatarTone:
    if mode is not DemoMode.AVATAR_MARKETING:
        return AvatarTone.PROFESSIONAL
    value = client_headers.get("x-client-avatar-tone") if client_headers else None
    if value is None or not value.strip():
        return AvatarTone.PROFESSIONAL
    try:
        return AvatarTone(value.strip().lower())
    except ValueError as exc:
        raise DemoModeError(f"Unsupported trusted avatar tone '{value}'.") from exc
