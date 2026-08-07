from __future__ import annotations

import logging
import os

from azure.monitor.opentelemetry import configure_azure_monitor

_CONTENT_RECORDING_SETTINGS = (
    "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT",
    "AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED",
    "AZURE_TRACING_GEN_AI_INCLUDE_BINARY_DATA",
)


def configure_logging(level: str) -> logging.Logger:
    for setting in _CONTENT_RECORDING_SETTINGS:
        os.environ[setting] = "false"
    connection_string = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
    if connection_string:
        configure_azure_monitor(
            connection_string=connection_string,
            logger_name="bank_servicing_agent",
            disable_offline_storage=True,
        )
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    return logging.getLogger("bank_servicing_agent")
