from logging import getLogger

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.controllers.game import (
    abort_game,
    create_game,
    get_active_game,
    get_game_by_id,
)
from bot.controllers.record import (
    create_record,
    get_record,
    get_remained_players_in_game,
    increase_player_buy_in,
    update_record,
)
from bot.services.game_finalization import finalize_game
from bot.controllers.user import (
    get_all_users,
    get_last_played_users,
    get_players_from_game,
    get_unplayed_users,
    get_user_from_db_by_tg_id,
)
from bot.internal.callbacks import (
    AbortDialogCbData,
    AddFundsOperationType,
    CancelCbData,
    FinishGameCbData,
    GameModeCbData,
    GameMenuCbData,
    SinglePlayerActionCbData,
    MultiselectFurtherCbData,
    PlayerCbData,
)
from bot.internal.lexicon import buttons, texts
from bot.internal.context import (
    Amount,
    FinalGameAction,
    GameAction,
    KeyboardMode,
    OperationType,
    RecordUpdateMode,
    States,
    SinglePlayerActionType,
)
from bot.internal.keyboards import (
    choose_single_player_kb,
    confirmation_dialog_kb,
    finish_game_kb,
    select_ratio_kb,
    users_multiselect_kb,
)
from database.models import Game, User

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
    logger.debug(
        "SinglePlayerAction: mode=%s player_id=%s user_id=%s",
        callback_data.mode, callback_data.player_id, callback.from_user.id
    )
    match callback_data.mode:
        case SinglePlayerActionType.CHOOSE_HOST:
            active_game = await get_active_game(db_session)
            if active_game:
                logger.warning("Attempt to create game while game %s is active", active_game.id)
                await callback.message.answer(text=texts["game_already_active"])
                return

            data = await state.get_data()
            ratio = data.get("next_game_ratio", 1)
            game = await create_game(
                admin_id=callback.from_user.id,
                host_id=callback_data.player_id,
                ratio=ratio,
                db_session=db_session,
            )
            logger.info("Game %s created by admin %s, host=%s, ratio=%s",
                game.id, callback.from_user.id, callback_data.player_id, ratio)
            await state.update_data(next_game_ratio=1)
            all_users = await get_all_users(db_session)
            last_played_users = await get_last_played_users(db_session)
            await state.update_data(chosen_for_new_game=last_played_users)
            await callback.message.answer(
                text=buttons["add_players"],
                reply_markup=users_multiselect_kb(
                    players=all_users,
                    mode=KeyboardMode.NEW_GAME,
                    game_id=game.id,
                    chosen=last_played_users,
                ),
            )
        case SinglePlayerActionType.ADD_FUNDS:
            last_played_users = await get_players_from_game(
                callback_data.game_id, db_session
            )
            await callback.message.answer(
                text=texts["add_funds_to_single_player"],
                reply_markup=choose_single_player_kb(
                    mode=SinglePlayerActionType.ADD_FUNDS,
                    players=last_played_users,
                    game_id=callback_data.game_id,
                ),
            )
        case SinglePlayerActionType.SET_BUY_OUT:
            await state.update_data(
                player_id=callback_data.player_id, game_id=callback_data.game_id
            )
            player = await get_user_from_db_by_tg_id(
                callback_data.player_id, db_session
            )
            await callback.message.answer(
                text=texts["admin_set_buyout_dialog"].format(player.fullname),
            )
            await state.set_state(States.ENTER_BUY_OUT)


@router.callback_query(PlayerCbData.filter())
async def players_multiselect_handler(
    callback: CallbackQuery,
    callback_data: PlayerCbData,
    state: FSMContext,
    db_session: AsyncSession,
) -> None:
    await callback.answer()
    data = await state.get_data()
    match callback_data.mode:
        case KeyboardMode.NEW_GAME:
            users = await get_all_users(db_session)
            chosen_users = data.get("chosen_for_new_game", list())
        case KeyboardMode.ADD_PLAYERS:
            users = await get_unplayed_users(db_session)
            chosen_users = data.get("chosen_for_add_players", list())
        case KeyboardMode.PLAYERS_ADD_1000:
            users = await get_players_from_game(callback_data.game_id, db_session)
            chosen_users = data.get("chosen_for_add_1000", list())
        case KeyboardMode.PLAYERS_WITH_0:
            users = await get_players_from_game(callback_data.game_id, db_session)
            chosen_users = data.get("chosen_for_players_with_0", list())
        case _:
            assert False, "Unexpected mode"

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


@router.callback_query(GameMenuCbData.filter())
async def game_menu_handler(
    callback: CallbackQuery,
    callback_data: GameMenuCbData,
    user: User,
    state: FSMContext,
    db_session: AsyncSession,
) -> None:
    await callback.answer()
    logger.debug("GameMenu: action=%s user_id=%s", callback_data.action, callback.from_user.id)
    all_users = await get_all_users(db_session)
    match callback_data.action:
        case GameAction.START_GAME:
            await callback.message.answer(
                text=texts["choose_host"],
                reply_markup=choose_single_player_kb(
                    mode=SinglePlayerActionType.CHOOSE_HOST, players=all_users
                ),
            )
        case GameAction.ADD_PLAYERS:
            await state.update_data(chosen_users=list())
            players_not_in_game = await get_unplayed_users(db_session)
            active_game: Game = await get_active_game(db_session)
            await callback.message.answer(
                text=buttons["add_players"],
                reply_markup=users_multiselect_kb(
                    players=players_not_in_game,
                    mode=KeyboardMode.ADD_PLAYERS,
                    game_id=active_game.id,
                ),
            )
        case GameAction.FINISH_GAME:
            active_game: Game = await get_active_game(db_session)
            await callback.message.answer(
                text=texts["finish_game_dialog"],
                reply_markup=finish_game_kb(active_game.id),
            )
        case GameAction.ABORT_GAME:
            active_game = await get_active_game(db_session)
            await callback.message.answer(
                text=texts["abort_game_dialog"].format(active_game.id),
                reply_markup=confirmation_dialog_kb(game_id=active_game.id),
            )
        case GameAction.ADD_FUNDS:
            active_game = await get_active_game(db_session)
            players = await get_players_from_game(active_game.id, db_session)
            await callback.message.answer(
                text=texts["add_funds_multiselect"],
                reply_markup=users_multiselect_kb(
                    players=players,
                    mode=KeyboardMode.PLAYERS_ADD_1000,
                    game_id=active_game.id,
                ),
            )
        case GameAction.ADD_PHOTO:
            await callback.message.answer(text=texts["add_photo"])
            await state.set_state(States.ADD_PHOTO)
        case GameAction.STATISTICS:
            match user.is_admin:
                case True:
                    await callback.message.answer(text=texts["admin_statistics"])
                case False:
                    await callback.message.answer(text=texts["user_statistics"])
        case GameAction.SELECT_RATIO:
            if user.is_admin:
                await callback.message.answer(
                    text=texts["select_mode_prompt"],
                    reply_markup=select_ratio_kb(),
                )
        case GameAction.SELECT_YEARLY_STATS:
            if user.is_admin:
                await state.update_data(next_game_yearly_stats=True)
                await callback.message.answer(text=texts["yearly_stats_set"])


@router.callback_query(GameModeCbData.filter())
async def game_mode_handler(
    callback: CallbackQuery,
    callback_data: GameModeCbData,
    state: FSMContext,
) -> None:
    await callback.answer()
    await state.update_data(next_game_ratio=callback_data.ratio)
    await callback.message.answer(text=texts["ratio_set"].format(callback_data.ratio))


@router.callback_query(CancelCbData.filter())
async def cancel_button_handler(
    callback: CallbackQuery,
    state: FSMContext,
    user: User,
    db_session: AsyncSession,
):
    await callback.answer()
    match user.is_admin:
        case True:
            ...
        case False:
            ...


@router.callback_query(MultiselectFurtherCbData.filter())
async def multiselect_further_handler(
    callback: CallbackQuery,
    callback_data: MultiselectFurtherCbData,
    state: FSMContext,
    db_session: AsyncSession,
) -> None:
    await callback.answer()
    logger.debug("MultiselectFurther: mode=%s game_id=%s user_id=%s",
        callback_data.mode, callback_data.game_id, callback.from_user.id)
    data = await state.get_data()
    users = await get_all_users(db_session)
    users_by_id = {user.id: user for user in users}
    match callback_data.mode:
        case KeyboardMode.NEW_GAME:
            game = await get_game_by_id(callback_data.game_id, db_session)
            host = users_by_id.get(game.host_id)
            chosen_users = data.get("chosen_for_new_game", list())
            await callback.bot.send_message(
                chat_id=settings.bot.GROUP_ID,
                text=texts["game_started_group"].format(
                    game_id=callback_data.game_id,
                    players_count=len(chosen_users),
                    host_name=host.fullname if host else "Unknown",
                ),
            )
            for user_id in chosen_users:
                record = await create_record(
                    game_id=callback_data.game_id,
                    user_id=user_id,
                    db_session=db_session,
                )
                user = users_by_id.get(user_id)
                if user:
                    user.last_time_played = True
                    user.games_played += 1
                db_session.add(record)
            for user in users:
                if user.id not in chosen_users:
                    user.last_time_played = False
            text = texts["admin_game_created"].format(callback_data.game_id)
            logger.info("Game %s: %d players added to new game", callback_data.game_id, len(chosen_users))
            await state.update_data(chosen_for_new_game=list())
        case KeyboardMode.ADD_PLAYERS:
            chosen_users = data.get("chosen_for_add_players", list())
            for user_id in chosen_users:
                record = await create_record(
                    game_id=callback_data.game_id,
                    user_id=user_id,
                    db_session=db_session,
                )
                user = users_by_id.get(user_id)
                if user:
                    user.last_time_played = True
                    user.games_played += 1
                db_session.add(record)
            text = texts["admin_players_added"].format(
                len(chosen_users), callback_data.game_id
            )
            logger.info("Game %s: %d players added mid-game", callback_data.game_id, len(chosen_users))
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
                    names.append(f"{user.fullname} ({buy_in})")
            text = texts["admin_1000_added_to_players"].format(
                callback_data.game_id, len(chosen_users), "\n".join(names)
            )
            logger.info("Game %s: 1000 added to %d players", callback_data.game_id, len(chosen_users))
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
            logger.info("Game %s: buy-out set to 0 for %d players", callback_data.game_id, len(chosen_users))
            await state.update_data(chosen_for_players_with_0=list())
        case _:
            assert False, "Unexpected mode"
    await callback.message.answer(text=text)


@router.callback_query(AddFundsOperationType.filter())
async def add_funds_handler(
    callback: CallbackQuery,
    callback_data: AddFundsOperationType,
    db_session: AsyncSession,
) -> None:
    await callback.answer()
    players = await get_players_from_game(callback_data.game_id, db_session)
    match callback_data.type:
        case OperationType.MULTISELECT:
            await callback.message.answer(
                text=buttons["multi_selector"],
                reply_markup=users_multiselect_kb(
                    players=players,
                    mode=KeyboardMode.PLAYERS_ADD_1000,
                    game_id=callback_data.game_id,
                ),
            )
        case _:
            await callback.message.answer(
                text=buttons["single_selector"],
                reply_markup=choose_single_player_kb(
                    SinglePlayerActionType.ADD_FUNDS, players, callback_data.game_id
                ),
            )


@router.callback_query(AbortDialogCbData.filter())
async def abort_game_handler(
    callback: CallbackQuery,
    callback_data: AbortDialogCbData,
    db_session: AsyncSession,
) -> None:
    await callback.answer()
    logger.info("Game %s aborted by user %s", callback_data.game_id, callback.from_user.id)
    await abort_game(callback_data.game_id, db_session)
    players: list[User] = await get_players_from_game(callback_data.game_id, db_session)
    for player in players:
        player.games_played -= 1
        db_session.add(player)
    await callback.message.answer(
        text=texts["abort_game_reply"].format(callback_data.game_id)
    )


@router.callback_query(FinishGameCbData.filter())
async def finish_game_handler(
    callback: CallbackQuery,
    callback_data: FinishGameCbData,
    state: FSMContext,
    db_session: AsyncSession,
) -> None:
    await callback.answer()
    logger.debug("FinishGame: action=%s game_id=%s user_id=%s",
        callback_data.action, callback_data.game_id, callback.from_user.id)
    match callback_data.action:
        case FinalGameAction.ADD_PLAYERS_WITH_0:
            active_players = await get_players_from_game(
                callback_data.game_id, db_session
            )
            await callback.message.answer(
                text=texts["admin_players_with_0_dialog"],
                reply_markup=users_multiselect_kb(
                    players=active_players,
                    mode=KeyboardMode.PLAYERS_WITH_0,
                    game_id=callback_data.game_id,
                ),
            )
        case FinalGameAction.ADD_PLAYERS_BUYOUT:
            players = await get_players_from_game(callback_data.game_id, db_session)
            await callback.message.answer(
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
                logger.warning("Game %s: finalization blocked, %d players without buy-out",
                    callback_data.game_id, remained_players)
                await callback.message.answer(
                    texts["remained_players"].format(
                        callback_data.game_id, remained_players
                    )
                )
            else:
                logger.info("Game %s: starting finalization", callback_data.game_id)
                result = await finalize_game(
                    game_id=callback_data.game_id,
                    bot=callback.bot,
                    state=state,
                    db_session=db_session,
                )
                if not result.success and result.error_message:
                    logger.error("Game %s: finalization failed - %s",
                        callback_data.game_id, result.error_message)
                    await callback.message.answer(text=result.error_message)
                else:
                    logger.info("Game %s: finalization completed successfully", callback_data.game_id)
