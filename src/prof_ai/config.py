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
    chat_daily_user_tokens: int = 50_000
    chat_daily_global_tokens: int = 500_000

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    def validate(self) -> None:
        if self.dev_user_id and (self.app_env != "local" or self.on_app_service):
            raise UnsafeConfigError("DEV_USER_ID is only allowed locally (APP_ENV=local).")


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
        chat_daily_user_tokens=int(os.getenv("CHAT_DAILY_USER_TOKENS", "50000")),
        chat_daily_global_tokens=int(os.getenv("CHAT_DAILY_GLOBAL_TOKENS", "500000")),
    )
