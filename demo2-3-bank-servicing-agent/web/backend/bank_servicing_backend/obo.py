from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Any, Callable, Protocol

import msal

from .config import EntraSettings
from .errors import OboExchangeError


class ConfidentialClientLike(Protocol):
    def acquire_token_on_behalf_of(self, user_assertion: str, scopes: Sequence[str]) -> dict[str, Any]: ...


class OboTokenProvider:
    def __init__(
        self,
        settings: EntraSettings,
        *,
        app_factory: Callable[[], ConfidentialClientLike] | None = None,
    ) -> None:
        self._settings = settings
        self._app_factory = app_factory or self._build_default_app

    async def acquire(self, user_assertion: str, scope: str = "https://ai.azure.com/.default") -> str:
        result = await asyncio.to_thread(
            self._app_factory().acquire_token_on_behalf_of,
            user_assertion,
            [scope],
        )
        token = result.get("access_token")
        if isinstance(token, str) and token:
            return token
        error = result.get("error") or "unknown_error"
        codes = ",".join(str(code) for code in (result.get("error_codes", []) or []))
        suffix = f" ({codes})" if codes else ""
        raise OboExchangeError(f"Microsoft Entra OBO exchange failed: {error}{suffix}")

    def _build_default_app(self) -> ConfidentialClientLike:
        return msal.ConfidentialClientApplication(
            client_id=self._settings.client_id,
            client_credential=self._settings.client_secret,
            authority=self._settings.authority,
        )
