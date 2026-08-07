from __future__ import annotations


class BridgeError(RuntimeError):
    status_code = 500
    error_code = "bridge_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ConfigurationError(BridgeError):
    status_code = 500
    error_code = "configuration_error"


class IdentityValidationError(BridgeError):
    status_code = 401
    error_code = "identity_validation_failed"


class ModeValidationError(BridgeError):
    status_code = 400
    error_code = "invalid_demo_mode"


class UpstreamError(BridgeError):
    status_code = 502
    error_code = "upstream_error"
