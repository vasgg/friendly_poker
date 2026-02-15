from logging import getLogger

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.controllers.game import abort_game
from bot.controllers.record import get_remained_players_in_game
from bot.controllers.user import get_players_from_game
from bot.handlers.callbacks.common import _edit_or_answer, _filter_users, _get_bot_id
from bot.internal.callbacks import AbortDialogCbData, FinishGameCbData
from bot.internal.context import FinalGameAction, KeyboardMode, SinglePlayerActionType
from bot.internal.keyboards import choose_single_player_kb, skip_photo_kb, users_multiselect_kb
from bot.internal.lexicon import texts
from bot.services.game_finalization import finalize_game
from bot.services.photo_reminder import (
    cancel_photo_reminder,
    game_has_photo,
    set_photo_warning,
)
from database.models import User

router = Router()
logger = getLogger(__name__)


@router.callback_query(AbortDialogCbData.filter())
async def abort_game_handler(
    callback: CallbackQuery,
    callback_data: AbortDialogCbData,
    db_session: AsyncSession,
) -> None:
    await callback.answer()
    logger.info(
        "Game %s aborted by user %s", callback_data.game_id, callback.from_user.id
    )
    cancel_photo_reminder(callback_data.game_id)
    await abort_game(callback_data.game_id, db_session)
    players: list[User] = await get_players_from_game(callback_data.game_id, db_session)
    for player in players:
        player.games_played -= 1
        db_session.add(player)
    await callback.message.answer(text=texts["abort_game_reply"].format(callback_data.game_id))


async def _do_finalize(
    callback: CallbackQuery,
    game_id: int,
    state: FSMContext,
    db_session: AsyncSession,
) -> None:
    logger.info("Game %s: starting finalization", game_id)
    result = await finalize_game(
        game_id=game_id,
        bot=callback.bot,
        state=state,
        db_session=db_session,
    )
    if not result.success and result.error_message:
        logger.error("Game %s: finalization failed - %s", game_id, result.error_message)
        await callback.message.answer(text=result.error_message)
    else:
        logger.info("Game %s: finalization completed successfully", game_id)


@router.callback_query(FinishGameCbData.filter())
async def finish_game_handler(
    callback: CallbackQuery,
    callback_data: FinishGameCbData,
    state: FSMContext,
    db_session: AsyncSession,
) -> None:
    await callback.answer()
    logger.debug(
        "FinishGame: action=%s game_id=%s user_id=%s",
        callback_data.action,
        callback_data.game_id,
        callback.from_user.id,
    )
    bot_id = await _get_bot_id(callback.bot)
    match callback_data.action:
        case FinalGameAction.ADD_PLAYERS_WITH_0:
            active_players = await get_players_from_game(callback_data.game_id, db_session)
            active_players = _filter_users(active_players, {bot_id})
            await _edit_or_answer(
                callback.message,
                text=texts["admin_players_with_0_dialog"],
                reply_markup=users_multiselect_kb(
                    players=active_players,
                    mode=KeyboardMode.PLAYERS_WITH_0,
                    game_id=callback_data.game_id,
                ),
            )
        case FinalGameAction.ADD_PLAYERS_BUYOUT:
            players = await get_players_from_game(callback_data.game_id, db_session)
            players = _filter_users(players, {bot_id})
            await _edit_or_answer(
                callback.message,
                text=texts["admin_players_buyout_dialog"],
                reply_markup=choose_single_player_kb(
                    mode=SinglePlayerActionType.SET_BUY_OUT,
                    players=players,
                    game_id=callback_data.game_id,
                ),
            )
        case FinalGameAction.FINALIZE_GAME:
            remained_players = await get_remained_players_in_game(
                callback_data.game_id, db_session
            )
            if remained_players:
                logger.warning(
                    "Game %s: finalization blocked, %d players without buy-out",
                    callback_data.game_id,
                    remained_players,
                )
                await callback.message.answer(
                    texts["remained_players"].format(callback_data.game_id, remained_players)
                )
            elif not game_has_photo(callback_data.game_id):
                msg = await callback.message.answer(
                    text=texts["photo_missing_warning"],
                    reply_markup=skip_photo_kb(callback_data.game_id),
                )
                set_photo_warning(callback_data.game_id, msg.message_id)
            else:
                await _do_finalize(callback, callback_data.game_id, state, db_session)
        case FinalGameAction.SKIP_PHOTO_AND_FINALIZE:
            await callback.message.delete()
            remained_players = await get_remained_players_in_game(
                callback_data.game_id, db_session
            )
            if remained_players:
                logger.warning(
                    "Game %s: finalization blocked, %d players without buy-out",
                    callback_data.game_id,
                    remained_players,
                )
                await callback.message.answer(
                    texts["remained_players"].format(callback_data.game_id, remained_players)
                )
            else:
                await _do_finalize(callback, callback_data.game_id, state, db_session)
