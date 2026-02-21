import logging
from pathlib import Path

from aiogram import F, Router
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.controllers.game import get_game_by_id
from bot.services.photo_reminder import clear_photo_warning, get_reminder_info, save_game_photo

logger = logging.getLogger(__name__)
router = Router()


@router.message(
    F.chat.id == settings.bot.GROUP_ID,
    F.reply_to_message,
)
async def handle_photo_reply(message: Message, db_session: AsyncSession) -> None:
    reply_msg_id = message.reply_to_message.message_id
    info = get_reminder_info(reply_msg_id)
    if info is None:
        return

    if message.from_user.id != info.admin_id:
        return

    has_photo = bool(message.photo)
    has_image_doc = (
        message.document is not None
        and message.document.mime_type is not None
        and message.document.mime_type.startswith("image/")
    )
    if not has_photo and not has_image_doc:
        return

    try:
        filepath = await save_game_photo(message.bot, message, info)
        photo_id = None
        if message.document:
            photo_id = message.document.file_id
        elif message.photo:
            photo_id = message.photo[-1].file_id

        game = await get_game_by_id(info.game_id, db_session)
        if game is not None and photo_id is not None:
            game.photo_name = Path(filepath).name
            game.photo_id = photo_id
            await db_session.flush()
            logger.info(
                "Game %s photo saved to DB: photo_name=%s",
                info.game_id,
                game.photo_name,
            )
        await clear_photo_warning(message.bot, info.game_id)
        await message.bot.send_message(
            chat_id=info.admin_id,
            text=f"Photo saved: {filepath}",
        )
        logger.info("Game %s photo saved by admin %s", info.game_id, message.from_user.id)
    except Exception:
        logger.exception("Failed to save photo for game %s", info.game_id)
