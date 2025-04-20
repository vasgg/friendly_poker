from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from bot.config import settings


class DatabaseConnector:
    def __init__(self, url: str, echo: bool = False) -> None:
        self.engine = create_async_engine(url=url, echo=echo)
        self.session_factory = async_sessionmaker(
            bind=self.engine,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )


def get_db() -> DatabaseConnector:
    return DatabaseConnector(url=settings.db.aiosqlite_db_url, echo=settings.db.echo)
