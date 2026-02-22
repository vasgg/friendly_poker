from zoneinfo import ZoneInfo

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings

from bot.internal.config_dicts import assign_config_dict


class BotConfig(BaseSettings):
    TOKEN: SecretStr
    ADMIN: int
    ADMIN_IBAN: str
    ADMIN_NAME: str
    GROUP_ID: int
    TIMEZONE: ZoneInfo = ZoneInfo("Asia/Tbilisi")

    model_config = assign_config_dict(prefix="BOT_")


class DBConfig(BaseSettings):
    FILE_NAME: str | None = None
    URL: str | None = None
    echo: bool = False

    model_config = assign_config_dict(prefix="DB_")

    @property
    def db_url(self) -> str:
        if self.URL:
            return self.URL
        return f"sqlite+aiosqlite:///{self.FILE_NAME}.db"

    @model_validator(mode="after")
    def validate_db_source(self):
        if self.URL:
            return self
        if self.FILE_NAME:
            return self
        raise ValueError("Either DB_URL or DB_FILE_NAME must be set")


class Settings(BaseSettings):
    bot: BotConfig = BotConfig()
    db: DBConfig = DBConfig()

    model_config = assign_config_dict()


settings = Settings()
