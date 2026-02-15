from zoneinfo import ZoneInfo

from pydantic import SecretStr
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
    FILE_NAME: str
    echo: bool = False

    model_config = assign_config_dict(prefix="DB_")

    @property
    def aiosqlite_db_url(self) -> str:
        return f"sqlite+aiosqlite:///{self.FILE_NAME}.db"


class Settings(BaseSettings):
    bot: BotConfig = BotConfig()
    db: DBConfig = DBConfig()

    model_config = assign_config_dict()


settings = Settings()
