from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Gartner Deep Research"
    data_dir: Path = Path("data")
    foundry_agent_endpoint: str | None = None
    foundry_agent_api_version: str = "v1"
    image_model_endpoint: str | None = None
    image_model_deployment: str = "flux-1-1-pro"
    speech_region: str | None = None
    speech_endpoint: str | None = None
    speech_resource_id: str | None = None
    speech_voice: str = "en-US-AvaMultilingualNeural"
    applicationinsights_connection_string: str | None = None
    allowed_origin: str = "http://localhost:5173"

    @property
    def database_path(self) -> Path:
        return self.data_dir / "runs.db"

    @property
    def artifacts_dir(self) -> Path:
        return self.data_dir / "runs"
