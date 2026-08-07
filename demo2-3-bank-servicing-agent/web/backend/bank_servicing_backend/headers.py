from __future__ import annotations

from collections.abc import Collection, Mapping

from .errors import ModeValidationError

TRACE_HEADERS = ("traceparent", "tracestate", "baggage")
DEMO_MODE_HEADER = "x-client-demo-mode"


def extract_forward_headers(
    headers: Mapping[str, str],
    *,
    allowed_demo_modes: Collection[str],
    demo_mode: str | None = None,
) -> dict[str, str]:
    canonical = {key.lower(): value for key, value in headers.items()}
    forwarded: dict[str, str] = {}

    header_mode = canonical.get(DEMO_MODE_HEADER)
    effective_mode = _resolve_demo_mode(header_mode, demo_mode)
    if effective_mode is not None:
        if effective_mode not in allowed_demo_modes:
            raise ModeValidationError(
                f"Unsupported x-client-demo-mode '{effective_mode}'. Expected one of: {', '.join(sorted(allowed_demo_modes))}"
            )
        forwarded[DEMO_MODE_HEADER] = effective_mode

    for header in TRACE_HEADERS:
        value = canonical.get(header)
        if value:
            forwarded[header] = value
    return forwarded


def _resolve_demo_mode(header_mode: str | None, body_mode: str | None) -> str | None:
    normalized_header = header_mode.strip() if header_mode else None
    normalized_body = body_mode.strip() if body_mode else None
    if normalized_header and normalized_body and normalized_header != normalized_body:
        raise ModeValidationError(
            "The x-client-demo-mode header does not match the request body mode"
        )
    return normalized_body or normalized_header
