from __future__ import annotations

import pytest

from bank_servicing_agent.modes import (
    AvatarTone,
    DemoMode,
    DemoModeError,
    resolve_avatar_tone,
    resolve_demo_mode,
)



def test_resolve_demo_mode_accepts_trusted_values() -> None:
    assert resolve_demo_mode({"x-client-demo-mode": "service_discovery"}) is DemoMode.SERVICE_DISCOVERY
    assert resolve_demo_mode({"x-client-demo-mode": "customer_servicing"}) is DemoMode.CUSTOMER_SERVICING
    assert resolve_demo_mode({"x-client-demo-mode": "avatar_marketing"}) is DemoMode.AVATAR_MARKETING



def test_resolve_demo_mode_rejects_unknown_value() -> None:
    with pytest.raises(DemoModeError):
        resolve_demo_mode({"x-client-demo-mode": "admin"})


def test_resolve_demo_mode_uses_trusted_default_only_when_header_is_missing() -> None:
    assert (
        resolve_demo_mode(None, trusted_default=DemoMode.AVATAR_MARKETING)
        is DemoMode.AVATAR_MARKETING
    )
    assert (
        resolve_demo_mode(
            {"x-client-demo-mode": "customer_servicing"},
            trusted_default=DemoMode.AVATAR_MARKETING,
        )
        is DemoMode.CUSTOMER_SERVICING
    )
    with pytest.raises(DemoModeError):
        resolve_demo_mode(
            {"x-client-demo-mode": "admin"},
            trusted_default=DemoMode.AVATAR_MARKETING,
        )


def test_avatar_tone_is_trusted_and_defaults_to_professional() -> None:
    assert resolve_avatar_tone(
        {"x-client-avatar-tone": "warm"},
        DemoMode.AVATAR_MARKETING,
    ) is AvatarTone.WARM
    assert resolve_avatar_tone({}, DemoMode.AVATAR_MARKETING) is AvatarTone.PROFESSIONAL
    assert resolve_avatar_tone(
        {"x-client-avatar-tone": "energetic"},
        DemoMode.CUSTOMER_SERVICING,
    ) is AvatarTone.PROFESSIONAL


def test_avatar_tone_rejects_unknown_header() -> None:
    with pytest.raises(DemoModeError):
        resolve_avatar_tone(
            {"x-client-avatar-tone": "impersonate"},
            DemoMode.AVATAR_MARKETING,
        )
