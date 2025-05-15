from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.controllers.debt import flush_debts_to_db, debt_informer_by_id
from bot.controllers.game import (
    abort_game,
    commit_game_results_to_db,
    create_game,
    get_active_game,
    get_game_by_id,
    get_group_game_report,
)
from bot.controllers.record import (
    check_game_balance,
    create_record,
    debt_calculator,
    get_mvp,
    get_roi_from_game_by_player_id,
    get_remained_players_in_game,
    increase_player_buy_in,
    update_net_profit_and_roi,
    update_record,
)
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
    mode_selector_kb,
    users_multiselect_kb,
)
from database.models import Game, User

router = Router()


@router.callback_query(SinglePlayerActionCbData.filter())
async def single_player_handler(
    callback: CallbackQuery,
    callback_data: SinglePlayerActionCbData,
    state: FSMContext,
    db_session: AsyncSession,
) -> None:
    await callback.answer()
    match callback_data.mode:
        case SinglePlayerActionType.CHOOSE_HOST:
            game = await create_game(
                admin_id=callback.from_user.id,
                host_id=callback_data.player_id,
                db_session=db_session,
            )
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
        case _:
            assert False, "Unexpected mode"


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
        case _:
            assert False, "Unexpected mode"
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
            await callback.message.answer(
                text=texts["add_funds_selector"],
                reply_markup=mode_selector_kb(game_id=active_game.id),
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
    data = await state.get_data()
    users = await get_all_users(db_session)
    match callback_data.mode:
        case KeyboardMode.NEW_GAME:
            game = await get_game_by_id(callback_data.game_id, db_session)
            host = await get_user_from_db_by_tg_id(game.host_id, db_session)
            chosen_users = data.get("chosen_for_new_game", list())
            await callback.bot.send_message(
                chat_id=settings.bot.GROUP_ID,
                text=texts["game_started_group"].format(
                    game_id=callback_data.game_id,
                    players_count=len(chosen_users),
                    host_name=host.fullname,
                ),
            )
            for user_id in chosen_users:
                record = await create_record(
                    game_id=callback_data.game_id,
                    user_id=user_id,
                    db_session=db_session,
                )
                user = await get_user_from_db_by_tg_id(user_id, db_session)
                user.last_time_played = True
                user.games_played += 1
                db_session.add_all([record, user])
            for user in users:
                if user.id not in chosen_users:
                    user.last_time_played = False
                    db_session.add(user)
            text = texts["admin_game_created"].format(callback_data.game_id)
            await state.update_data(chosen_for_new_game=list())
        case KeyboardMode.ADD_PLAYERS:
            chosen_users = data.get("chosen_for_add_players", list())
            for user_id in chosen_users:
                record = await create_record(
                    game_id=callback_data.game_id,
                    user_id=user_id,
                    db_session=db_session,
                )
                user = await get_user_from_db_by_tg_id(user_id, db_session)
                user.last_time_played = True
                user.games_played += 1
                db_session.add_all([record, user])
            text = texts["admin_players_added"].format(
                len(chosen_users), callback_data.game_id
            )
            await state.update_data(chosen_for_add_players=list())
        case KeyboardMode.PLAYERS_ADD_1000:
            chosen_users = data.get("chosen_for_add_1000", list())
            for user_id in chosen_users:
                await increase_player_buy_in(
                    user_id=user_id,
                    game_id=callback_data.game_id,
                    amount=Amount.ONE_THOUSAND,
                    db_session=db_session,
                )
            text = texts["admin_1000_added_to_players"].format(
                callback_data.game_id, len(chosen_users)
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
            await state.update_data(chosen_for_players_with_0=list())
        case _:
            assert False, "Unexpected mode"
    await callback.message.answer(text=text)


@router.callback_query(AddFundsOperationType.filter())
async def add_funds_handler(
    callback: CallbackQuery,
    callback_data: AddFundsOperationType,
    user: User,
    state: FSMContext,
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
    db_session: AsyncSession,
) -> None:
    await callback.answer()
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
                await callback.message.answer(
                    texts["remained_players"].format(
                        callback_data.game_id, remained_players
                    )
                )
            else:
                results = await check_game_balance(callback_data.game_id, db_session)
                if not results.total_pot or not results.delta:
                    await callback.message.answer(texts["check_game_balance_error"])
                if results.delta != 0:
                    await callback.message.answer(
                        text=texts["exit_game_wrong_total_sum"].format(
                            results.total_pot, results.delta
                        )
                    )
                else:
                    await update_net_profit_and_roi(callback_data.game_id, db_session)
                    transactions = await debt_calculator(
                        callback_data.game_id, db_session
                    )
                    mvp = await get_mvp(callback_data.game_id, db_session)
                    mvp_player: User = await get_user_from_db_by_tg_id(mvp, db_session)
                    await commit_game_results_to_db(
                        callback_data.game_id, results.total_pot, mvp, db_session
                    )
                    mvp_roi = await get_roi_from_game_by_player_id(
                        callback_data.game_id, mvp, db_session
                    )
                    text = await get_group_game_report(
                        callback_data.game_id, mvp_player.fullname, mvp_roi, db_session
                    )
                    await flush_debts_to_db(transactions, db_session)
                    await debt_informer_by_id(
                        callback_data.game_id, callback, db_session
                    )
                    await callback.bot.send_message(
                        chat_id=settings.bot.GROUP_ID, text=text
                    )
