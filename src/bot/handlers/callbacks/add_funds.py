import html
from logging import getLogger

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.controllers.game import get_active_game
from bot.controllers.record import get_record, increase_player_buy_in
from bot.controllers.user import get_players_from_game, get_user_from_db_by_tg_id
from bot.handlers.callbacks.common import _edit_or_answer, _filter_users, _get_bot_id
from bot.internal.callbacks import AddFundsOperationType, CustomFundsConfirmCbData
from bot.internal.context import KeyboardMode, OperationType, SinglePlayerActionType, States
from bot.internal.keyboards import choose_single_player_kb, users_multiselect_kb
from bot.internal.lexicon import texts

router = Router()
logger = getLogger(__name__)


@router.callback_query(AddFundsOperationType.filter())
async def add_funds_handler(
    callback: CallbackQuery,
    callback_data: AddFundsOperationType,
    db_session: AsyncSession,
) -> None:
    await callback.answer()
    logger.info(
        "Add funds mode selected: game_id=%s mode=%s user_id=%s",
        callback_data.game_id,
        callback_data.type,
        callback.from_user.id,
    )
    bot_id = await _get_bot_id(callback.bot)
    players = _filter_users(
        await get_players_from_game(callback_data.game_id, db_session), {bot_id}
    )
    match callback_data.type:
        case OperationType.MULTISELECT:
            await _edit_or_answer(
                callback.message,
                text=texts["add_funds_multiselect"],
                reply_markup=users_multiselect_kb(
                    players=players,
                    mode=KeyboardMode.PLAYERS_ADD_1000,
                    game_id=callback_data.game_id,
                ),
            )
        case _:
            await _edit_or_answer(
                callback.message,
                text=texts["add_funds_to_single_player"],
                reply_markup=choose_single_player_kb(
                    SinglePlayerActionType.ADD_FUNDS, players, callback_data.game_id
                ),
            )


@router.callback_query(CustomFundsConfirmCbData.filter())
async def custom_funds_confirm_handler(
    callback: CallbackQuery,
    callback_data: CustomFundsConfirmCbData,
    state: FSMContext,
    db_session: AsyncSession,
) -> None:
    await callback.answer()
    data = await state.get_data()
    player_id = data.get("custom_funds_player_id")
    game_id = data.get("custom_funds_game_id")
    amount = data.get("custom_funds_amount")
    if not player_id or not game_id or amount is None:
        await callback.message.answer(text=texts["custom_funds_not_ready"])
        return
    active_game = await get_active_game(db_session)
    if not active_game or active_game.id != game_id:
        await state.update_data(
            custom_funds_player_id=None,
            custom_funds_game_id=None,
            custom_funds_amount=None,
        )
        await state.set_state()
        await callback.message.answer(text=texts["no_active_game"])
        return
    record = await get_record(game_id, player_id, db_session)
    if record is None:
        await state.update_data(
            custom_funds_player_id=None,
            custom_funds_game_id=None,
            custom_funds_amount=None,
        )
        await state.set_state()
        await callback.message.answer(text=texts["custom_funds_not_ready"])
        return
    player = await get_user_from_db_by_tg_id(player_id, db_session)
    if player is None:
        await callback.message.answer(text=texts["custom_funds_not_ready"])
        return
    if not callback_data.confirm:
        logger.info(
            "Custom funds confirm rejected: game_id=%s player_id=%s admin_id=%s amount=%s",
            game_id,
            player_id,
            callback.from_user.id,
            amount,
        )
        await state.update_data(custom_funds_amount=None)
        await _edit_or_answer(
            callback.message,
            text=texts["custom_funds_amount_prompt"].format(html.escape(player.fullname)),
        )
        await state.set_state(States.ENTER_CUSTOM_FUNDS)
        return

    await increase_player_buy_in(
        user_id=player_id,
        game_id=game_id,
        amount=amount,
        db_session=db_session,
    )
    record = await get_record(game_id, player_id, db_session)
    buy_in = record.buy_in if record and record.buy_in is not None else 0
    await state.update_data(
        custom_funds_player_id=None,
        custom_funds_game_id=None,
        custom_funds_amount=None,
    )
    await state.set_state()
    logger.info(
        "Custom funds applied: game_id=%s player_id=%s admin_id=%s amount=%s buy_in=%s",
        game_id,
        player_id,
        callback.from_user.id,
        amount,
        buy_in,
    )
    await callback.message.answer(
        text=texts["custom_funds_applied"].format(
            game_id,
            amount,
            html.escape(player.fullname),
            buy_in,
        )
    )
