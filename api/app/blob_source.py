from azure.core.exceptions import ResourceNotFoundError
from azure.storage.blob import BlobServiceClient, ContainerClient

from .config import Settings

LATEST_BLOB = "v1/latest.json"


class BlobAggregatesSource:
    """Reads v1/latest.json from the private aggregates container (D-18)."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._container: ContainerClient | None = None

    def _client(self) -> ContainerClient:
        if self._container is None:
            s = self._settings
            if s.azure_storage_connection_string:
                service = BlobServiceClient.from_connection_string(s.azure_storage_connection_string)
            elif s.storage_account_url:
                from azure.identity import DefaultAzureCredential  # deferred: slow import, cloud-only path

                service = BlobServiceClient(s.storage_account_url, credential=DefaultAzureCredential())
            else:
                raise RuntimeError("set AZURE_STORAGE_CONNECTION_STRING (local) or STORAGE_ACCOUNT_URL (cloud)")
            self._container = service.get_container_client(s.aggregates_container)
        return self._container

    def fetch(self) -> bytes | None:
        try:
            return self._client().download_blob(LATEST_BLOB).readall()
        except ResourceNotFoundError:
            return None
