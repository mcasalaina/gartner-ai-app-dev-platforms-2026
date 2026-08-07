from __future__ import annotations

import os

from azure.monitor.opentelemetry import configure_azure_monitor


def configure_telemetry() -> bool:
    connection_string = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
    if not connection_string:
        return False
    configure_azure_monitor(
        connection_string=connection_string,
        logger_name="bank_servicing_bridge",
        disable_offline_storage=True,
    )
    return True
