"""Secrets come from the environment locally and from Azure Key Vault in the cloud."""

from functools import lru_cache
from typing import Protocol

from app.config import get_settings

# Key Vault secret names cannot contain underscores, so JWT_SECRET is stored as "jwt-secret".
_ENV_FIELDS = {
    "jwt-secret": "jwt_secret",
    "anthropic-api-key": "anthropic_api_key",
}


class SecretProvider(Protocol):
    def get(self, name: str) -> str: ...


class EnvSecretProvider:
    def get(self, name: str) -> str:
        return str(getattr(get_settings(), _ENV_FIELDS[name]))


class KeyVaultSecretProvider:
    def __init__(self, vault_url: str) -> None:
        from azure.identity import DefaultAzureCredential
        from azure.keyvault.secrets import SecretClient

        self._client = SecretClient(vault_url=vault_url, credential=DefaultAzureCredential())
        self._cache: dict[str, str] = {}

    def get(self, name: str) -> str:
        if name not in self._cache:
            self._cache[name] = self._client.get_secret(name).value or ""
        return self._cache[name]


@lru_cache
def get_secrets() -> SecretProvider:
    settings = get_settings()
    if settings.secrets_backend == "keyvault":
        return KeyVaultSecretProvider(settings.key_vault_url)
    return EnvSecretProvider()
