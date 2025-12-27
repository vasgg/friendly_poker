import html
import logging
import os

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError

from bot.config import Settings, settings

logger = logging.getLogger(__name__)


async def on_startup(bot: Bot, settings: Settings):
    folder = os.path.basename(os.getcwd())
    try:
        await bot.send_message(
            settings.bot.ADMIN,
            f"<b>{folder.replace('_', ' ')} started</b>\n\n/start",
            disable_notification=True,
        )
    except:
        logger.warning("Failed to send on shutdown notify")


async def on_shutdown(bot: Bot, settings: Settings):
    folder = os.path.basename(os.getcwd())
    try:
        await bot.send_message(
            settings.bot.ADMIN,
            f"<b>{folder.replace('_', ' ')} shutdown</b>",
            disable_notification=True,
        )
    except:
        logger.warning("Failed to send on shutdown notify")


async def notify_admin_blocked_message(
    bot: Bot, fullname: str, text: str
) -> None:
    warning_text = (
        "<b>Message delivery failed</b>\n"
        f"User: <b>{html.escape(fullname)}</b>\n"
        "<b>Message:</b>\n"
        f"<pre>{html.escape(text)}</pre>"
    )
    try:
        await bot.send_message(
            settings.bot.ADMIN,
            warning_text,
            disable_web_page_preview=True,
            parse_mode="HTML",
        )
    except Exception:
        logger.warning("Failed to notify admin about blocked user message")


async def send_message_to_player(
    bot: Bot, user_id: int, fullname: str, text: str, **kwargs
):
    try:
        return await bot.send_message(chat_id=user_id, text=text, **kwargs)
    except TelegramForbiddenError:
        logger.warning(
            "User blocked bot. fullname=%s message=%r",
            fullname,
            text,
        )
        await notify_admin_blocked_message(bot, fullname, text)
        return None
