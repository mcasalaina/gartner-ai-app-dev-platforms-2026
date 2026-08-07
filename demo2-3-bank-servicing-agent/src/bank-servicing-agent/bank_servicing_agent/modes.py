from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum


class DemoMode(StrEnum):
    SERVICE_DISCOVERY = "service_discovery"
    CUSTOMER_SERVICING = "customer_servicing"


class DemoModeError(ValueError):
    """Raised when the trusted operating mode is missing or invalid."""



def resolve_demo_mode(client_headers: Mapping[str, str] | None) -> DemoMode:
    if not client_headers:
        raise DemoModeError(
            "Missing required trusted operating mode. Supported values are "
            "service_discovery and customer_servicing."
        )
    value = client_headers.get("x-client-demo-mode")
    if value is None or not value.strip():
        raise DemoModeError(
            "Missing required trusted operating mode. Supported values are "
            "service_discovery and customer_servicing."
        )
    normalized = value.strip().lower()
    try:
        return DemoMode(normalized)
    except ValueError as exc:
        raise DemoModeError(
            f"Unsupported trusted operating mode '{value}'. Supported values are "
            "service_discovery and customer_servicing."
        ) from exc
