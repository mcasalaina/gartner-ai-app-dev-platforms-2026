from __future__ import annotations


class BackendError(RuntimeError):
    """Base class for expected backend failures."""

    status_code = 500
    error_code = "backend_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ConfigurationError(BackendError):
    status_code = 500
    error_code = "configuration_error"


class AuthenticationError(BackendError):
    status_code = 401
    error_code = "authentication_failed"


class AuthorizationError(BackendError):
    status_code = 403
    error_code = "authorization_failed"


class NotFoundError(BackendError):
    status_code = 404
    error_code = "not_found"


class ModeValidationError(BackendError):
    status_code = 400
    error_code = "invalid_demo_mode"


class OboExchangeError(BackendError):
    status_code = 502
    error_code = "obo_exchange_failed"


class UpstreamInvocationError(BackendError):
    status_code = 502
    error_code = "upstream_invocation_failed"


class VoiceHandleError(BackendError):
    status_code = 401
    error_code = "voice_handle_invalid"
