from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from bank_servicing_agent.credentials import managed_identity_environment
from bank_servicing_agent.modes import DemoMode


@dataclass(frozen=True, slots=True)
class Agent365WorkIQSettings:
    tenant_id: str
    blueprint_client_id: str
    blueprint_secret_vault_url: str
    blueprint_secret_name: str
    instance_client_id: str
    agent_user_id: str
    mail_mcp_url: str
    mail_mcp_audience: str


@dataclass(frozen=True, slots=True)
class Settings:
    project_endpoint: str
    model_deployment: str
    toolbox_endpoint: str | None
    toolbox_name: str | None
    instructions_path: Path
    log_level: str
    agent_name: str
    agent_version: str | None
    trusted_default_demo_mode: DemoMode | None
    agent365_work_iq: Agent365WorkIQSettings | None

    @classmethod
    def from_environment(cls) -> "Settings":
        dotenv_path = os.getenv("DOTENV_PATH")
        load_dotenv(dotenv_path=dotenv_path or None)
        project_endpoint = _required_any_environment_variable(
            "FOUNDRY_PROJECT_ENDPOINT",
            "AZURE_AI_PROJECT_ENDPOINT",
        )
        model_deployment = _resolve_model_deployment_name(project_endpoint)
        instructions_path = Path(os.getenv("AGENT_INSTRUCTIONS_PATH", "instructions.md"))
        if not instructions_path.is_file():
            raise FileNotFoundError(
                f"Agent instructions file does not exist: {instructions_path}"
            )
        toolbox_endpoint = os.getenv("TOOLBOX_ENDPOINT") or None
        toolbox_name = os.getenv("TOOLBOX_NAME") or None
        if not toolbox_endpoint and not toolbox_name:
            raise RuntimeError(
                "Required environment variable is not set. Expected TOOLBOX_ENDPOINT or TOOLBOX_NAME"
            )
        agent365_work_iq = _optional_agent365_work_iq_settings()
        return cls(
            project_endpoint=project_endpoint.rstrip("/"),
            model_deployment=model_deployment,
            toolbox_endpoint=toolbox_endpoint,
            toolbox_name=toolbox_name,
            instructions_path=instructions_path,
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
            agent_name=os.getenv("FOUNDRY_AGENT_NAME", "bank-servicing-agent"),
            agent_version=os.getenv("FOUNDRY_AGENT_VERSION") or None,
            trusted_default_demo_mode=_optional_demo_mode(
                "TRUSTED_DEFAULT_DEMO_MODE"
            ),
            agent365_work_iq=agent365_work_iq,
        )



def _required_any_environment_variable(*names: str) -> str:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    joined = ", ".join(names)
    raise RuntimeError(f"Required environment variable is not set. Expected one of: {joined}")



def _resolve_model_deployment_name(project_endpoint: str) -> str:
    model_name = os.getenv("AZURE_AI_MODEL_DEPLOYMENT_NAME")
    if model_name:
        return model_name
    if managed_identity_environment():
        raise RuntimeError(
            "Required environment variable is not set: AZURE_AI_MODEL_DEPLOYMENT_NAME"
        )
    if not project_endpoint:
        raise RuntimeError("FOUNDRY_PROJECT_ENDPOINT must be set before model resolution")
    return "gpt-5.4-mini"


def _optional_demo_mode(name: str) -> DemoMode | None:
    value = os.getenv(name, "").strip().lower()
    if not value:
        return None
    try:
        return DemoMode(value)
    except ValueError as exc:
        supported = ", ".join(mode.value for mode in DemoMode)
        raise RuntimeError(
            f"Unsupported {name} value '{value}'. Expected one of: {supported}"
        ) from exc


def _optional_agent365_work_iq_settings() -> Agent365WorkIQSettings | None:
    environment_names = {
        "tenant_id": "AGENT365_TENANT_ID",
        "blueprint_client_id": "AGENT365_BLUEPRINT_CLIENT_ID",
        "blueprint_secret_vault_url": "AGENT365_BLUEPRINT_SECRET_VAULT_URL",
        "blueprint_secret_name": "AGENT365_BLUEPRINT_SECRET_NAME",
        "instance_client_id": "AGENT365_INSTANCE_CLIENT_ID",
        "agent_user_id": "AGENT365_AGENT_USER_ID",
        "mail_mcp_url": "WORK_IQ_MAIL_MCP_URL",
        "mail_mcp_audience": "WORK_IQ_MAIL_MCP_AUDIENCE",
    }
    values = {
        field_name: os.getenv(environment_name, "").strip()
        for field_name, environment_name in environment_names.items()
    }
    if not any(values.values()):
        return None
    missing = [
        environment_names[field_name]
        for field_name, value in values.items()
        if not value
    ]
    if missing:
        raise RuntimeError(
            "Agent 365 Work IQ configuration is incomplete. Missing: "
            + ", ".join(sorted(missing))
        )
    return Agent365WorkIQSettings(**values)
