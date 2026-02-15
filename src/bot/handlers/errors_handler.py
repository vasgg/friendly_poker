import html
import logging
import traceback

import aiogram
from aiogram import Router
from aiogram.types import ErrorEvent

from bot.config import Settings

router = Router()


@router.errors()
async def error_handler(error_event: ErrorEvent, bot: aiogram.Bot, settings: Settings):
    exc_info = error_event.exception
    exc_traceback = "".join(
        traceback.format_exception(None, exc_info, exc_info.__traceback__),
    )
    tb = exc_traceback[-3500:]
    tb_escaped = html.escape(tb)
    exc_type = html.escape(type(exc_info).__name__)
    exc_message = html.escape(str(exc_info))

    error_message = (
        "<b>Error</b>\n\n"
        f"<b>Type:</b> {exc_type}\n"
        f"<b>Message:</b> {exc_message}\n\n"
        f"<b>Traceback:</b>\n<code>{tb_escaped}</code>"
    )
    logging.exception("Exception: ", exc_info=exc_info)

    try:
        await bot.send_message(settings.bot.ADMIN, error_message)
    except Exception:
        logging.exception("Failed to send error message to admin")
