import html
from logging import getLogger

from aiogram import Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.controllers.game import (
    get_next_game_settings,
    update_next_game_ratio,
    update_next_game_yearly_stats,
)
from bot.handlers.callbacks.common import _edit_or_answer
from bot.internal.callbacks import (
    GameModeCbData,
    NextGameRatioConfirmCbData,
    NextGameYearlyStatsConfirmCbData,
)
from bot.internal.keyboards import next_game_menu_kb, ratio_confirm_kb, select_ratio_kb
from bot.internal.lexicon import texts
from database.models import User

router = Router()
logger = getLogger(__name__)


@router.callback_query(GameModeCbData.filter())
async def game_mode_handler(
    callback: CallbackQuery,
    callback_data: GameModeCbData,
    user: User,
    db_session: AsyncSession,
) -> None:
    await callback.answer()
    if not user.is_admin:
        await callback.message.answer(text=texts["insufficient_privileges"])
        return
    next_game_settings = await get_next_game_settings(db_session)
    if callback_data.version != next_game_settings.version:
        await _edit_or_answer(
            callback.message,
            text=texts["next_game_settings_stale"],
            reply_markup=next_game_menu_kb(),
        )
        return
    await _edit_or_answer(
        callback.message,
        text=texts["ratio_confirm"].format(callback_data.ratio),
        reply_markup=ratio_confirm_kb(callback_data.ratio, callback_data.version),
    )


@router.callback_query(NextGameRatioConfirmCbData.filter())
async def next_game_ratio_confirm_handler(
    callback: CallbackQuery,
    callback_data: NextGameRatioConfirmCbData,
    user: User,
    db_session: AsyncSession,
) -> None:
    await callback.answer()
    if not user.is_admin:
        await callback.message.answer(text=texts["insufficient_privileges"])
        return
    if callback_data.confirm:
        next_game_settings = await update_next_game_ratio(
            ratio=callback_data.ratio,
            expected_version=callback_data.version,
            admin_id=callback.from_user.id,
            admin_name=user.fullname,
            db_session=db_session,
        )
        if next_game_settings is None:
            logger.warning(
                "Stale next game ratio confirmation rejected: admin_id=%s ratio=%s expected_version=%s",
                callback.from_user.id,
                callback_data.ratio,
                callback_data.version,
            )
            await _edit_or_answer(
                callback.message,
                text=texts["next_game_settings_stale"],
                reply_markup=next_game_menu_kb(),
            )
            return
        logger.info(
            "Next game ratio confirmed: admin_id=%s username=%s ratio=%s version=%s",
            callback.from_user.id,
            callback.from_user.username,
            callback_data.ratio,
            next_game_settings.version,
        )
        try:
            await callback.bot.send_message(
                chat_id=settings.bot.GROUP_ID,
                text=texts["ratio_set_group"].format(
                    ratio=callback_data.ratio,
                    admin_name=html.escape(user.fullname),
                ),
            )
        except Exception:
            logger.exception(
                "Failed to send next game ratio group notification: admin_id=%s ratio=%s",
                callback.from_user.id,
                callback_data.ratio,
            )
        await _edit_or_answer(
            callback.message,
            text=texts["ratio_set"].format(callback_data.ratio),
            reply_markup=next_game_menu_kb(),
        )
        return
    next_game_settings = await get_next_game_settings(db_session)
    await _edit_or_answer(
        callback.message,
        text=texts["select_mode_prompt"],
        reply_markup=select_ratio_kb(next_game_settings.version),
    )


@router.callback_query(NextGameYearlyStatsConfirmCbData.filter())
async def next_game_yearly_stats_confirm_handler(
    callback: CallbackQuery,
    callback_data: NextGameYearlyStatsConfirmCbData,
    user: User,
    db_session: AsyncSession,
) -> None:
    await callback.answer()
    if not user.is_admin:
        await callback.message.answer(text=texts["insufficient_privileges"])
        return
    next_game_settings = await update_next_game_yearly_stats(
        enabled=callback_data.confirm,
        expected_version=callback_data.version,
        admin_id=callback.from_user.id,
        admin_name=user.fullname,
        db_session=db_session,
    )
    if next_game_settings is None:
        logger.warning(
            "Stale next game yearly-stats update rejected: admin_id=%s enabled=%s expected_version=%s",
            callback.from_user.id,
            callback_data.confirm,
            callback_data.version,
        )
        await _edit_or_answer(
            callback.message,
            text=texts["next_game_settings_stale"],
            reply_markup=next_game_menu_kb(),
        )
        return
    logger.info(
        "Next game yearly stats updated: admin_id=%s username=%s enabled=%s version=%s",
        callback.from_user.id,
        callback.from_user.username,
        callback_data.confirm,
        next_game_settings.version,
    )
    if callback_data.confirm:
        text = texts["yearly_stats_set"]
    else:
        text = texts["yearly_stats_unset"]
    await _edit_or_answer(
        callback.message,
        text=text,
        reply_markup=next_game_menu_kb(),
    )
