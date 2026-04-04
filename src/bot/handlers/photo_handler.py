import logging
from pathlib import Path

from aiogram import F, Router
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.controllers.game import get_game_by_id
from bot.controllers.record import get_record
from bot.internal.lexicon import texts
from bot.services.photo_reminder import (
    cancel_photo_reminder,
    clear_photo_warning,
    get_reminder_info,
    save_game_photo,
)

logger = logging.getLogger(__name__)
router = Router()


def _user_label(message: Message) -> str:
    user = message.from_user
    if user is None:
        return "Unknown"
    full_name = getattr(user, "full_name", None)
    if full_name:
        return full_name
    username = getattr(user, "username", None)
    if username:
        return f"@{username}"
    return str(user.id)


async def _notify_photo_saved(message: Message, game_id: int, admin_id: int, filepath: str) -> None:
    recipients = {message.from_user.id, admin_id}
    uploader_label = _user_label(message)
    for recipient_id in recipients:
        if recipient_id == message.from_user.id:
            text = texts["photo_saved_player"].format(game_id=game_id, filepath=filepath)
        else:
            text = texts["photo_saved_admin"].format(
                game_id=game_id,
                uploader_label=uploader_label,
                filepath=filepath,
            )
        try:
            await message.bot.send_message(chat_id=recipient_id, text=text)
        except Exception:
            logger.exception(
                "Game %s photo saved, but failed to notify user %s",
                game_id,
                recipient_id,
            )


async def _notify_photo_failure(message: Message, game_id: int, admin_id: int, exc: Exception) -> None:
    uploader_label = _user_label(message)
    uploader_id = message.from_user.id
    admin_text = texts["photo_save_failed_admin"].format(
        game_id=game_id,
        uploader_label=uploader_label,
        uploader_id=uploader_id,
        error_type=type(exc).__name__,
        error_message=exc,
    )
    try:
        await message.bot.send_message(chat_id=admin_id, text=admin_text)
    except Exception:
        logger.exception(
            "Game %s photo save failed, but failed to notify admin %s",
            game_id,
            admin_id,
        )
    if uploader_id == admin_id:
        return
    try:
        await message.bot.send_message(
            chat_id=uploader_id,
            text=texts["photo_save_failed_player"].format(game_id=game_id),
        )
    except Exception:
        logger.exception(
            "Game %s photo save failed, but failed to notify uploader %s",
            game_id,
            uploader_id,
        )


@router.message(
    F.chat.id == settings.bot.GROUP_ID,
    F.reply_to_message,
)
async def handle_photo_reply(message: Message, db_session: AsyncSession) -> None:
    if message.from_user is None:
        return

    reply_msg_id = message.reply_to_message.message_id
    info = get_reminder_info(reply_msg_id)
    if info is None:
        return

    has_photo = bool(message.photo)
    has_image_doc = (
        message.document is not None
        and message.document.mime_type is not None
        and message.document.mime_type.startswith("image/")
    )
    if not has_photo and not has_image_doc:
        return
    if await get_record(info.game_id, message.from_user.id, db_session) is None:
        await message.answer(texts["photo_upload_forbidden"].format(game_id=info.game_id))
        return

    filepath: str | None = None
    try:
        filepath = await save_game_photo(message.bot, message, info)
        photo_id = None
        if message.document:
            photo_id = message.document.file_id
        elif message.photo:
            photo_id = message.photo[-1].file_id

        game = await get_game_by_id(info.game_id, db_session)
        if game is None or photo_id is None:
            raise ValueError(f"Game {info.game_id} not found while saving photo")
        game.photo_name = Path(filepath).name
        game.photo_id = photo_id
        await db_session.flush()
        logger.info(
            "Game %s photo saved to DB: photo_name=%s",
            info.game_id,
            game.photo_name,
        )
    except Exception as exc:
        if filepath is not None:
            try:
                Path(filepath).unlink(missing_ok=True)
            except Exception:
                logger.exception("Failed to remove partially saved photo for game %s", info.game_id)
        logger.exception("Failed to save photo for game %s", info.game_id)
        await _notify_photo_failure(message, info.game_id, info.admin_id, exc)
        return

    await clear_photo_warning(message.bot, info.game_id)
    cancel_photo_reminder(info.game_id)
    await _notify_photo_saved(message, info.game_id, info.admin_id, filepath)
    logger.info("Game %s photo saved by user %s", info.game_id, message.from_user.id)
