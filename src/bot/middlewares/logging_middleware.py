import functools
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject


class LoggingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        try:
            name = self._get_name(handler)
        except Exception:
            logging.exception("Failed to resolve handler name")
            name = repr(handler)
        logging.info("calling %s", name)
        return await handler(event, data)

    def _get_name(self, handler):
        while isinstance(handler, functools.partial):
            if not handler.args:
                break
            handler = handler.args[0]

        wrapped = getattr(handler, "__wrapped__", None)
        if wrapped is not None:
            owner = getattr(wrapped, "__self__", None)
            callback = getattr(owner, "callback", None) if owner else None
            if callback is not None:
                return getattr(callback, "__name__", repr(callback))
        return getattr(handler, "__name__", repr(handler))
