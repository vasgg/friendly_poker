from zoneinfo import ZoneInfo

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings
from sqlalchemy.engine import make_url

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
    URL: SecretStr
    echo: bool = False

    model_config = assign_config_dict(prefix="DB_")

    @field_validator("URL")
    @classmethod
    def validate_url(cls, value: SecretStr) -> SecretStr:
        raw = value.get_secret_value()
        try:
            parsed = make_url(raw)
        except Exception as exc:  # pragma: no cover - defensive validation
            raise ValueError("DB_URL must be a valid SQLAlchemy URL") from exc

        if parsed.get_backend_name() != "postgresql":
            raise ValueError("DB_URL must use PostgreSQL backend")
        if parsed.get_driver_name() != "asyncpg":
            raise ValueError("DB_URL must use asyncpg driver (postgresql+asyncpg://...)")
        return value

    @property
    def db_url(self) -> str:
        return self.URL.get_secret_value()


class Settings(BaseSettings):
    bot: BotConfig = BotConfig()
    db: DBConfig = DBConfig()

    model_config = assign_config_dict()


settings = Settings()
