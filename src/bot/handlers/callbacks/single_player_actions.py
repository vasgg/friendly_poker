import html
from logging import getLogger

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.controllers.game import get_active_game
from bot.controllers.user import (
    get_all_users,
    get_last_played_users,
    get_user_from_db_by_tg_id,
)
from bot.handlers.callbacks.common import (
    _edit_or_answer,
    _filter_ids,
    _filter_users,
    _get_bot_id,
)
from bot.internal.callbacks import SinglePlayerActionCbData
from bot.internal.context import KeyboardMode, SinglePlayerActionType, States
from bot.internal.keyboards import users_multiselect_kb
from bot.internal.lexicon import buttons, texts

router = Router()
logger = getLogger(__name__)


@router.callback_query(SinglePlayerActionCbData.filter())
async def single_player_handler(
    callback: CallbackQuery,
    callback_data: SinglePlayerActionCbData,
    state: FSMContext,
    db_session: AsyncSession,
) -> None:
    await callback.answer()
    bot_id = await _get_bot_id(callback.bot)
    logger.debug(
        "SinglePlayerAction: mode=%s player_id=%s user_id=%s",
        callback_data.mode,
        callback_data.player_id,
        callback.from_user.id,
    )
    match callback_data.mode:
        case SinglePlayerActionType.CHOOSE_HOST:
            active_game = await get_active_game(db_session)
            if active_game:
                logger.warning(
                    "Attempt to create game while game %s is active", active_game.id
                )
                await callback.message.answer(text=texts["game_already_active"])
                return

            await state.update_data(next_game_host_id=callback_data.player_id)
            all_users = _filter_users(await get_all_users(db_session), {bot_id})
            last_played_users = _filter_ids(await get_last_played_users(db_session), bot_id)
            await state.update_data(chosen_for_new_game=last_played_users)
            await _edit_or_answer(
                callback.message,
                text=buttons["add_players"],
                reply_markup=users_multiselect_kb(
                    players=all_users,
                    mode=KeyboardMode.NEW_GAME,
                    game_id=0,
                    chosen=last_played_users,
                ),
            )
        case SinglePlayerActionType.ADD_FUNDS:
            await state.update_data(
                custom_funds_player_id=callback_data.player_id,
                custom_funds_game_id=callback_data.game_id,
            )
            player = await get_user_from_db_by_tg_id(callback_data.player_id, db_session)
            if player is None:
                await callback.message.answer(text=texts["custom_funds_not_ready"])
                return
            logger.info(
                "Custom funds target selected: game_id=%s player_id=%s admin_id=%s",
                callback_data.game_id,
                callback_data.player_id,
                callback.from_user.id,
            )
            await _edit_or_answer(
                callback.message,
                text=texts["custom_funds_amount_prompt"].format(html.escape(player.fullname)),
            )
            await state.set_state(States.ENTER_CUSTOM_FUNDS)
        case SinglePlayerActionType.SET_BUY_OUT:
            await state.update_data(
                player_id=callback_data.player_id,
                game_id=callback_data.game_id,
            )
            player = await get_user_from_db_by_tg_id(callback_data.player_id, db_session)
            player_name = html.escape(player.fullname) if player else "Unknown"
            await _edit_or_answer(
                callback.message,
                text=texts["admin_set_buyout_dialog"].format(player_name),
            )
            await state.set_state(States.ENTER_BUY_OUT)
