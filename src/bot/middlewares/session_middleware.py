from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from database.database_connector import DatabaseConnector


class DBSessionMiddleware(BaseMiddleware):
    def __init__(self, db: DatabaseConnector):
        self.db = db

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        async with self.db.session_factory() as db_session:
            data["db_session"] = db_session
            try:
                res = await handler(event, data)
            except Exception:
                await db_session.rollback()
                raise
            else:
                await db_session.commit()
            return res
