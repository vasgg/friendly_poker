import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.dispatcher.event.bases import UNHANDLED
from aiogram.types import TelegramObject

logger = logging.getLogger(__name__)


class UpdatesDumperMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        json_event = event.model_dump_json(exclude_unset=True)

        logger.debug(json_event)
        res = await handler(event, data)
        if res is UNHANDLED:
            logger.debug("UNHANDLED")
        return res
