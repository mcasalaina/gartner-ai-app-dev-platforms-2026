from __future__ import annotations

import pytest

from bank_servicing_agent.modes import DemoMode, DemoModeError, resolve_demo_mode



def test_resolve_demo_mode_accepts_trusted_values() -> None:
    assert resolve_demo_mode({"x-client-demo-mode": "service_discovery"}) is DemoMode.SERVICE_DISCOVERY
    assert resolve_demo_mode({"x-client-demo-mode": "customer_servicing"}) is DemoMode.CUSTOMER_SERVICING



def test_resolve_demo_mode_rejects_unknown_value() -> None:
    with pytest.raises(DemoModeError):
        resolve_demo_mode({"x-client-demo-mode": "admin"})
