from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All configuration comes from environment variables or `.env`."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "DriveNow"
    version: str = "1.0.0"
    commit: str = ""
    environment: str = "local"

    database_url: str = "sqlite+aiosqlite:///./drivenow.db"

    secrets_backend: Literal["env", "keyvault"] = "env"
    key_vault_url: str = ""
    jwt_secret: str = "change-me-local-only-secret-of-32-plus-characters"
    jwt_expire_minutes: int = 120

    storage_backend: Literal["azure", "local"] = "azure"
    azure_storage_connection_string: str = (
        "DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;"
        "AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;"
        "BlobEndpoint=http://127.0.0.1:10000/devstoreaccount1;"
    )
    photo_container: str = "car-photos"
    local_storage_dir: str = "./storage"

    messaging_backend: Literal["servicebus", "memory"] = "memory"
    servicebus_connection_string: str = (
        "Endpoint=sb://localhost;SharedAccessKeyName=RootManageSharedAccessKey;"
        "SharedAccessKey=SAS_KEY_VALUE;UseDevelopmentEmulator=true;"
    )
    booking_topic: str = "booking-events"

    llm_provider: Literal["anthropic", "mock"] = "mock"
    llm_model: str = "claude-haiku-5-5"
    anthropic_api_key: str = ""

    drivenow_bugs: Literal["on", "off"] = "on"

    seed_password: str = "DriveNow!2026"
    seed_on_start: bool = False

    otel_exporter_otlp_endpoint: str = ""

    @property
    def bugs_on(self) -> bool:
        return self.drivenow_bugs == "on"


@lru_cache
def get_settings() -> Settings:
    return Settings()
