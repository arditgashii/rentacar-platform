"""Car photos live in Azure Blob Storage (Azurite locally). `local` keeps them on disk for unit tests."""

import contextlib
from pathlib import Path
from typing import Protocol

from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
from azure.storage.blob import ContentSettings
from azure.storage.blob.aio import BlobServiceClient

from app.config import get_settings


class PhotoStorage(Protocol):
    async def start(self) -> None: ...
    async def close(self) -> None: ...
    async def upload(self, name: str, data: bytes, content_type: str) -> None: ...
    async def download(self, name: str) -> tuple[bytes, str] | None: ...
    async def delete(self, name: str) -> None: ...
    async def exists(self, name: str) -> bool: ...
    async def ping(self) -> None: ...


class AzureBlobStorage:
    def __init__(self, connection_string: str, container: str) -> None:
        self._service = BlobServiceClient.from_connection_string(connection_string)
        self._container = self._service.get_container_client(container)

    async def start(self) -> None:
        with contextlib.suppress(ResourceExistsError):
            await self._container.create_container()

    async def close(self) -> None:
        await self._service.close()

    async def upload(self, name: str, data: bytes, content_type: str) -> None:
        await self._container.upload_blob(
            name, data, overwrite=True, content_settings=ContentSettings(content_type=content_type)
        )

    async def download(self, name: str) -> tuple[bytes, str] | None:
        try:
            stream = await self._container.download_blob(name)
        except ResourceNotFoundError:
            return None
        content_type = stream.properties.content_settings.content_type or "application/octet-stream"
        return await stream.readall(), content_type

    async def delete(self, name: str) -> None:
        with contextlib.suppress(ResourceNotFoundError):
            await self._container.delete_blob(name)

    async def exists(self, name: str) -> bool:
        return bool(await self._container.get_blob_client(name).exists())

    async def ping(self) -> None:
        await self._container.get_container_properties()


class LocalStorage:
    def __init__(self, root: str) -> None:
        self._root = Path(root)

    def _path(self, name: str) -> Path:
        return self._root / name

    async def start(self) -> None:
        self._root.mkdir(parents=True, exist_ok=True)

    async def close(self) -> None:
        pass

    async def upload(self, name: str, data: bytes, content_type: str) -> None:
        path = self._path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        path.with_suffix(path.suffix + ".type").write_text(content_type)

    async def download(self, name: str) -> tuple[bytes, str] | None:
        path = self._path(name)
        if not path.is_file():
            return None
        return path.read_bytes(), path.with_suffix(path.suffix + ".type").read_text()

    async def delete(self, name: str) -> None:
        path = self._path(name)
        path.unlink(missing_ok=True)
        path.with_suffix(path.suffix + ".type").unlink(missing_ok=True)

    async def exists(self, name: str) -> bool:
        return self._path(name).is_file()

    async def ping(self) -> None:
        if not self._root.is_dir():
            raise RuntimeError(f"{self._root} does not exist")


def build_storage() -> PhotoStorage:
    settings = get_settings()
    if settings.storage_backend == "local":
        return LocalStorage(settings.local_storage_dir)
    return AzureBlobStorage(settings.azure_storage_connection_string, settings.photo_container)
