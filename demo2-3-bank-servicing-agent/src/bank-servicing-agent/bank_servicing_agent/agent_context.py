from __future__ import annotations

from contextvars import ContextVar, Token

_platform_user_id: ContextVar[str | None] = ContextVar(
    "platform_user_id",
    default=None,
)


def current_platform_user_id() -> str:
    user_id = _platform_user_id.get()
    if not user_id:
        raise RuntimeError("The request has no authenticated platform user context")
    return user_id


def set_platform_user_id(user_id: str | None) -> Token[str | None]:
    return _platform_user_id.set(user_id)


def reset_platform_user_id(token: Token[str | None]) -> None:
    _platform_user_id.reset(token)
