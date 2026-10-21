import os
from dataclasses import dataclass


class UnsafeConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class Settings:
    app_env: str
    cosmos_endpoint: str = ""
    dev_user_id: str = ""
    on_app_service: bool = False
    platform_auth_enabled: bool = False
    foundry_endpoint: str = ""
    chat_deployment: str = ""
    storage_account_url: str = ""
    chat_enabled: bool = True
    chat_daily_user_usd: float = 0.50
    chat_daily_global_usd: float = 1.50
    chat_tokens_per_minute: int = 50_000
    ollama_api_key: str = ""

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    def validate(self) -> None:
        if self.dev_user_id and (self.app_env != "local" or self.on_app_service):
            raise UnsafeConfigError("DEV_USER_ID is only allowed locally (APP_ENV=local).")


def secret_setting(name: str) -> str:
    """An app setting holding a secret. An unresolved Key Vault reference counts as unset."""
    value = os.getenv(name, "").strip()
    return "" if value.startswith("@Microsoft.KeyVault(") else value


def load_settings() -> Settings:
    return Settings(
        app_env=os.getenv("APP_ENV", "local"),
        cosmos_endpoint=os.getenv("COSMOS_ENDPOINT", ""),
        dev_user_id=os.getenv("DEV_USER_ID", ""),
        on_app_service=bool(os.getenv("WEBSITE_SITE_NAME")),
        platform_auth_enabled=os.getenv("WEBSITE_AUTH_ENABLED", "").lower() == "true",
        foundry_endpoint=os.getenv("FOUNDRY_ENDPOINT", ""),
        chat_deployment=os.getenv("CHAT_DEPLOYMENT", ""),
        storage_account_url=os.getenv("STORAGE_ACCOUNT_URL", ""),
        chat_enabled=os.getenv("CHAT_ENABLED", "true").lower() == "true",
        chat_daily_user_usd=float(os.getenv("CHAT_DAILY_USER_USD", "0.50")),
        chat_daily_global_usd=float(os.getenv("CHAT_DAILY_GLOBAL_USD", "1.50")),
        chat_tokens_per_minute=int(os.getenv("CHAT_TOKENS_PER_MINUTE", "50000")),
        ollama_api_key=secret_setting("OLLAMA_API_KEY"),
    )
