import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    app_env: str

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


def load_settings() -> Settings:
    return Settings(app_env=os.getenv("APP_ENV", "local"))
