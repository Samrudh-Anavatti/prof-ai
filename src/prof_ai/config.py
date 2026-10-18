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
    )
