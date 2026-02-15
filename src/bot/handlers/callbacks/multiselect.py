import html
from logging import getLogger

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.controllers.game import create_game, get_active_game
from bot.controllers.record import (
    create_record,
    get_record,
    increase_player_buy_in,
    update_record,
)
from bot.controllers.user import (
    get_all_users,
    get_players_from_game,
    get_unplayed_users,
)
from bot.handlers.callbacks.common import _filter_ids, _filter_users, _get_bot_id
from bot.internal.callbacks import MultiselectFurtherCbData, PlayerCbData
from bot.internal.context import Amount, KeyboardMode, RecordUpdateMode
from bot.internal.keyboards import users_multiselect_kb
from bot.internal.lexicon import texts
from bot.services.photo_reminder import schedule_photo_reminder

router = Router()
logger = getLogger(__name__)


@router.callback_query(PlayerCbData.filter())
async def players_multiselect_handler(
    callback: CallbackQuery,
    callback_data: PlayerCbData,
    state: FSMContext,
    db_session: AsyncSession,
) -> None:
    await callback.answer()
    bot_id = await _get_bot_id(callback.bot)
    if callback_data.player_id == bot_id:
        return
    data = await state.get_data()
    match callback_data.mode:
        case KeyboardMode.NEW_GAME:
            users = await get_all_users(db_session)
            chosen_users = _filter_ids(data.get("chosen_for_new_game", list()), bot_id)
        case KeyboardMode.ADD_PLAYERS:
            users = await get_unplayed_users(db_session)
            chosen_users = _filter_ids(
                data.get("chosen_for_add_players", list()), bot_id
            )
        case KeyboardMode.PLAYERS_ADD_1000:
            users = await get_players_from_game(callback_data.game_id, db_session)
            chosen_users = _filter_ids(data.get("chosen_for_add_1000", list()), bot_id)
        case KeyboardMode.PLAYERS_WITH_0:
            users = await get_players_from_game(callback_data.game_id, db_session)
            chosen_users = _filter_ids(
                data.get("chosen_for_players_with_0", list()), bot_id
            )
        case _:
            raise ValueError("Unexpected mode")

    users = _filter_users(users, {bot_id})
    if bot_id in chosen_users:
        chosen_users = [user_id for user_id in chosen_users if user_id != bot_id]

    if callback_data.player_id in chosen_users:
        chosen_users.remove(callback_data.player_id)
    else:
        chosen_users.append(callback_data.player_id)

    match callback_data.mode:
        case KeyboardMode.NEW_GAME:
            await state.update_data(chosen_for_new_game=chosen_users)
        case KeyboardMode.ADD_PLAYERS:
            await state.update_data(chosen_for_add_players=chosen_users)
        case KeyboardMode.PLAYERS_ADD_1000:
            await state.update_data(chosen_for_add_1000=chosen_users)
        case KeyboardMode.PLAYERS_WITH_0:
            await state.update_data(chosen_for_players_with_0=chosen_users)
    await callback.message.edit_reply_markup(
        reply_markup=users_multiselect_kb(
            players=users,
            mode=callback_data.mode,
            game_id=callback_data.game_id,
            chosen=chosen_users,
        ),
    )


@router.callback_query(MultiselectFurtherCbData.filter())
async def multiselect_further_handler(
    callback: CallbackQuery,
    callback_data: MultiselectFurtherCbData,
    state: FSMContext,
    db_session: AsyncSession,
) -> None:
    await callback.answer()
    logger.debug(
        "MultiselectFurther: mode=%s game_id=%s user_id=%s",
        callback_data.mode,
        callback_data.game_id,
        callback.from_user.id,
    )
    bot_id = await _get_bot_id(callback.bot)
    data = await state.get_data()
    users = _filter_users(await get_all_users(db_session), {bot_id})
    users_by_id = {user.id: user for user in users}
    match callback_data.mode:
        case KeyboardMode.NEW_GAME:
            host_id = data.get("next_game_host_id")
            if not host_id:
                await callback.message.answer(text=texts["host_not_selected"])
                return
            if await get_active_game(db_session):
                await callback.message.answer(text=texts["game_already_active"])
                return
            ratio = data.get("next_game_ratio", 1)
            game = await create_game(
                admin_id=callback.from_user.id,
                host_id=host_id,
                ratio=ratio,
                db_session=db_session,
            )
            if game is None:
                await callback.message.answer(text=texts["game_already_active"])
                return
            host = users_by_id.get(host_id)
            schedule_photo_reminder(
                bot=callback.bot,
                game_id=game.id,
                admin_id=callback.from_user.id,
                admin_username=callback.from_user.username,
                host_fullname=host.fullname if host else "unknown",
                game_created_at=game.created_at,
            )
            await state.update_data(next_game_ratio=1, next_game_host_id=None)
            chosen_users = _filter_ids(data.get("chosen_for_new_game", list()), bot_id)
            await callback.bot.send_message(
                chat_id=settings.bot.GROUP_ID,
                text=texts["game_started_group"].format(
                    game_id=game.id,
                    players_count=len(chosen_users),
                    host_name=html.escape(host.fullname) if host else "Unknown",
                ),
            )
            for user_id in chosen_users:
                record = await create_record(
                    game_id=game.id,
                    user_id=user_id,
                    db_session=db_session,
                    flush=False,
                )
                user = users_by_id.get(user_id)
                if user:
                    user.last_time_played = True
                    user.games_played += 1
                db_session.add(record)
            for user in users:
                if user.id not in chosen_users:
                    user.last_time_played = False
            await db_session.flush()
            text = texts["admin_game_created"].format(game.id)
            logger.info(
                "Game %s: %d players added to new game",
                game.id,
                len(chosen_users),
            )
            await state.update_data(chosen_for_new_game=list())
        case KeyboardMode.ADD_PLAYERS:
            chosen_users = data.get("chosen_for_add_players", list())
            for user_id in chosen_users:
                record = await create_record(
                    game_id=callback_data.game_id,
                    user_id=user_id,
                    db_session=db_session,
                    flush=False,
                )
                user = users_by_id.get(user_id)
                if user:
                    user.last_time_played = True
                    user.games_played += 1
                db_session.add(record)
            await db_session.flush()
            text = texts["admin_players_added"].format(
                len(chosen_users), callback_data.game_id
            )
            logger.info(
                "Game %s: %d players added mid-game",
                callback_data.game_id,
                len(chosen_users),
            )
            await state.update_data(chosen_for_add_players=list())
        case KeyboardMode.PLAYERS_ADD_1000:
            chosen_users = data.get("chosen_for_add_1000", list())
            names = []
            for user_id in chosen_users:
                await increase_player_buy_in(
                    user_id=user_id,
                    game_id=callback_data.game_id,
                    amount=Amount.ONE_THOUSAND,
                    db_session=db_session,
                )
                user = users_by_id.get(user_id)
                record = await get_record(callback_data.game_id, user_id, db_session)
                if user:
                    buy_in = record.buy_in if record else 0
                    names.append(f"{html.escape(user.fullname)} ({buy_in})")
            text = texts["admin_1000_added_to_players"].format(
                callback_data.game_id, len(chosen_users), "\n".join(names)
            )
            logger.info(
                "Game %s: 1000 added to %d players",
                callback_data.game_id,
                len(chosen_users),
            )
            await state.update_data(chosen_for_add_1000=list())
        case KeyboardMode.PLAYERS_WITH_0:
            chosen_users = data.get("chosen_for_players_with_0", list())
            for user_id in chosen_users:
                await update_record(
                    game_id=callback_data.game_id,
                    user_id=user_id,
                    mode=RecordUpdateMode.UPDATE_BUY_OUT,
                    value=0,
                    db_session=db_session,
                )
            text = texts["admin_players_with_0"].format(
                callback_data.game_id, len(chosen_users)
            )
            logger.info(
                "Game %s: buy-out set to 0 for %d players",
                callback_data.game_id,
                len(chosen_users),
            )
            await state.update_data(chosen_for_players_with_0=list())
        case _:
            raise ValueError("Unexpected mode")
    await callback.message.answer(text=text)
