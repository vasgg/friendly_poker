from logging import getLogger

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.controllers.game import (
    generate_all_time_stats_report,
    get_active_game,
    get_all_time_stats,
)
from bot.controllers.user import (
    get_all_users,
    get_non_admin_users,
    get_unplayed_users,
)
from bot.handlers.callbacks.common import (
    _edit_or_answer,
    _filter_users,
    _get_bot_id,
    _paginate_players,
)
from bot.internal.admin_menu import build_admin_menu
from bot.internal.callbacks import CancelCbData, GameMenuCbData
from bot.internal.context import GameAction, KeyboardMode, SinglePlayerActionType
from bot.internal.keyboards import (
    choose_single_player_kb,
    confirmation_dialog_kb,
    delete_player_list_kb,
    finish_game_kb,
    game_menu_kb,
    mode_selector_kb,
    next_game_menu_kb,
    select_ratio_kb,
    users_multiselect_kb,
    yearly_stats_confirm_kb,
)
from bot.internal.lexicon import buttons, texts
from database.models import User

router = Router()
logger = getLogger(__name__)


@router.callback_query(GameMenuCbData.filter())
async def game_menu_handler(
    callback: CallbackQuery,
    callback_data: GameMenuCbData,
    user: User,
    state: FSMContext,
    db_session: AsyncSession,
) -> None:
    await callback.answer()
    logger.debug(
        "GameMenu: action=%s user_id=%s", callback_data.action, callback.from_user.id
    )
    bot_id = await _get_bot_id(callback.bot)
    all_users = _filter_users(await get_all_users(db_session), {bot_id})
    match callback_data.action:
        case GameAction.START_GAME:
            await _edit_or_answer(
                callback.message,
                text=texts["choose_host"],
                reply_markup=choose_single_player_kb(
                    mode=SinglePlayerActionType.CHOOSE_HOST, players=all_users
                ),
            )
        case GameAction.ADD_PLAYERS:
            active_game = await get_active_game(db_session)
            if not active_game:
                await callback.message.answer(text=texts["no_active_game"])
                return
            await state.update_data(chosen_users=list())
            players_not_in_game = _filter_users(await get_unplayed_users(db_session), {bot_id})
            await _edit_or_answer(
                callback.message,
                text=buttons["add_players"],
                reply_markup=users_multiselect_kb(
                    players=players_not_in_game,
                    mode=KeyboardMode.ADD_PLAYERS,
                    game_id=active_game.id,
                ),
            )
        case GameAction.FINISH_GAME:
            active_game = await get_active_game(db_session)
            if not active_game:
                await callback.message.answer(text=texts["no_active_game"])
                return
            await _edit_or_answer(
                callback.message,
                text=texts["finish_game_dialog"],
                reply_markup=finish_game_kb(active_game.id),
            )
        case GameAction.ABORT_GAME:
            active_game = await get_active_game(db_session)
            if not active_game:
                await callback.message.answer(text=texts["no_active_game"])
                return
            await _edit_or_answer(
                callback.message,
                text=texts["abort_game_dialog"].format(active_game.id),
                reply_markup=confirmation_dialog_kb(game_id=active_game.id),
            )
        case GameAction.ADD_FUNDS:
            active_game = await get_active_game(db_session)
            if not active_game:
                await callback.message.answer(text=texts["no_active_game"])
                return
            logger.info(
                "Add funds menu opened: game_id=%s user_id=%s",
                active_game.id,
                callback.from_user.id,
            )
            await _edit_or_answer(
                callback.message,
                text=texts["add_funds_selector"],
                reply_markup=mode_selector_kb(active_game.id),
            )
        case GameAction.STATISTICS:
            if not user.is_admin:
                await callback.message.answer(text=texts["insufficient_privileges"])
                return
            summary, players = await get_all_time_stats(db_session)
            report = generate_all_time_stats_report(summary, players)
            await callback.message.answer(text=report)
        case GameAction.NEXT_GAME_SETTINGS:
            if user.is_admin:
                await _edit_or_answer(
                    callback.message,
                    text=texts["admin_next_game_menu"],
                    reply_markup=next_game_menu_kb(),
                )
        case GameAction.SELECT_RATIO:
            if user.is_admin:
                await _edit_or_answer(
                    callback.message,
                    text=texts["select_mode_prompt"],
                    reply_markup=select_ratio_kb(),
                )
        case GameAction.SELECT_YEARLY_STATS:
            if user.is_admin:
                await _edit_or_answer(
                    callback.message,
                    text=texts["yearly_stats_confirm"],
                    reply_markup=yearly_stats_confirm_kb(),
                )
        case GameAction.DELETE_PLAYER:
            if not user.is_admin:
                await callback.message.answer(text=texts["insufficient_privileges"])
                return
            players = await get_non_admin_users(
                db_session,
                exclude_ids={callback.from_user.id, bot_id},
            )
            if not players:
                await callback.message.answer(text=texts["admin_delete_player_no_players"])
                return
            page_players, total_pages, page = _paginate_players(players, 0)
            await _edit_or_answer(
                callback.message,
                text=texts["admin_delete_player_dialog"],
                reply_markup=delete_player_list_kb(
                    players=page_players,
                    page=page,
                    total_pages=total_pages,
                ),
            )


@router.callback_query(CancelCbData.filter())
async def admin_cancel_handler(
    callback: CallbackQuery,
    user: User,
    state: FSMContext,
    db_session: AsyncSession,
) -> None:
    await callback.answer()
    if not user.is_admin:
        await callback.message.answer(text=texts["insufficient_privileges"])
        return
    data = await state.get_data()
    saved_ratio = data.get("next_game_ratio")
    saved_yearly = data.get("next_game_yearly_stats")
    await state.clear()
    updates = {}
    if saved_ratio is not None:
        updates["next_game_ratio"] = saved_ratio
    if saved_yearly:
        updates["next_game_yearly_stats"] = saved_yearly
    if updates:
        await state.update_data(**updates)
    text, status = await build_admin_menu(db_session)
    await _edit_or_answer(
        callback.message,
        text=text,
        reply_markup=game_menu_kb(status=status, is_admin=user.is_admin),
    )
