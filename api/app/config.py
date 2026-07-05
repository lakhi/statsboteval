from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Credential modes (D-28): connection string for local Azurite; account URL +
    # DefaultAzureCredential (managed identity) in the cloud. Exactly one is set.
    azure_storage_connection_string: str | None = None
    storage_account_url: str | None = None

    aggregates_container: str = "aggregates"
    cache_ttl_seconds: int = 300
    schema_path: Path = _REPO_ROOT / "schema" / "aggregates.schema.json"
    dashboard_dist: Path | None = None
