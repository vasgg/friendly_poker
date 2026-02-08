import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from aiogram import Bot
from aiogram.errors import TelegramBadRequest
from aiogram.types import Message

from bot.config import settings

logger = logging.getLogger(__name__)

PHOTO_REMINDER_DELAY = 2 * 60 * 60  # 2 hours

_tasks: dict[int, asyncio.Task] = {}


@dataclass
class ReminderInfo:
    game_id: int
    admin_id: int
    admin_username: str | None
    host_fullname: str
    game_created_at: datetime


_reminders: dict[int, ReminderInfo] = {}
_photo_warnings: dict[int, int] = {}  # game_id → warning message_id


def get_reminder_info(message_id: int) -> ReminderInfo | None:
    return _reminders.get(message_id)


def game_has_photo(game_id: int) -> bool:
    return any(Path("photos").glob(f"**/game{game_id}_*"))


def set_photo_warning(game_id: int, message_id: int) -> None:
    _photo_warnings[game_id] = message_id


async def clear_photo_warning(bot: Bot, game_id: int) -> None:
    msg_id = _photo_warnings.pop(game_id, None)
    if msg_id:
        try:
            await bot.delete_message(chat_id=settings.bot.GROUP_ID, message_id=msg_id)
        except TelegramBadRequest:
            logger.debug("Could not delete photo warning message %s", msg_id)


def schedule_photo_reminder(
    bot: Bot,
    game_id: int,
    admin_id: int,
    admin_username: str | None,
    host_fullname: str,
    game_created_at: datetime,
) -> None:
    info = ReminderInfo(
        game_id=game_id,
        admin_id=admin_id,
        admin_username=admin_username,
        host_fullname=host_fullname,
        game_created_at=game_created_at,
    )
    task = asyncio.create_task(_reminder_task(bot, info))
    _tasks[game_id] = task
    logger.info("Photo reminder scheduled for game %s in %s seconds", game_id, PHOTO_REMINDER_DELAY)


def cancel_photo_reminder(game_id: int) -> None:
    task = _tasks.pop(game_id, None)
    if task is not None:
        task.cancel()
    expired = [msg_id for msg_id, info in _reminders.items() if info.game_id == game_id]
    for msg_id in expired:
        del _reminders[msg_id]
    _photo_warnings.pop(game_id, None)
    if task is not None or expired:
        logger.info("Photo reminder cancelled for game %s", game_id)


async def _reminder_task(bot: Bot, info: ReminderInfo) -> None:
    try:
        await asyncio.sleep(PHOTO_REMINDER_DELAY)
    except asyncio.CancelledError:
        return

    try:
        if info.admin_username:
            mention = f"@{info.admin_username}"
        else:
            mention = f'<a href="tg://user?id={info.admin_id}">Admin</a>'
        text = f"Game #{info.game_id}: don't forget to take a photo! {mention}"
        msg = await bot.send_message(
            chat_id=settings.bot.GROUP_ID,
            text=text,
            disable_notification=True,
        )
        _reminders[msg.message_id] = info
        logger.info("Photo reminder sent for game %s (message_id=%s)", info.game_id, msg.message_id)
    except Exception:
        logger.exception("Failed to send photo reminder for game %s", info.game_id)
    finally:
        _tasks.pop(info.game_id, None)


async def save_game_photo(bot: Bot, message: Message, info: ReminderInfo) -> str:
    if message.document and message.document.mime_type and message.document.mime_type.startswith("image/"):
        file_id = message.document.file_id
        original_name = message.document.file_name or ""
        ext = Path(original_name).suffix if original_name else ".jpg"
    elif message.photo:
        file_id = message.photo[-1].file_id
        ext = ".jpg"
    else:
        raise ValueError("Message has no photo or image document")

    created_at = info.game_created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    local_dt = created_at.astimezone(settings.bot.TIMEZONE)

    date_str = local_dt.strftime("%d_%m_%Y")
    year_str = str(local_dt.year)
    host_safe = info.host_fullname.replace(" ", "_")
    filename = f"game{info.game_id}_{date_str}_{host_safe}{ext}"

    photo_dir = Path("photos") / year_str
    photo_dir.mkdir(parents=True, exist_ok=True)
    filepath = photo_dir / filename

    # Remove previous photo for this game (different extension possible)
    pattern = f"game{info.game_id}_{date_str}_{host_safe}.*"
    for old_file in photo_dir.glob(pattern):
        old_file.unlink()
        logger.info("Removed previous photo: %s", old_file)

    file = await bot.get_file(file_id)
    await bot.download_file(file.file_path, destination=filepath)
    logger.info("Photo saved: %s", filepath)
    return str(filepath)
