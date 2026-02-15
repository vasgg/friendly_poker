from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from bot.config import settings
from bot.controllers.user import add_user_to_db, get_user_from_db_by_tg_id


class AuthMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user_payload = getattr(event, "from_user", None)
        if user_payload is None:
            return await handler(event, data)
        db_session = data["db_session"]
        user = await get_user_from_db_by_tg_id(user_payload.id, db_session)
        if not user:
            is_admin = user_payload.id == settings.bot.ADMIN
            user = await add_user_to_db(user_payload, db_session, is_admin)
        data["user"] = user
        return await handler(event, data)
