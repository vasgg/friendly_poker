import html
import math
from contextlib import suppress
from datetime import UTC
from logging import getLogger

from aiogram import Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.config import settings
from bot.controllers.debt import (
    calculate_debt_amount,
    get_unpaid_debts_as_creditor,
    get_unpaid_debts_as_debtor,
)
from bot.controllers.game import (
    abort_game,
    create_game,
    generate_all_time_stats_report,
    get_active_game,
    get_all_time_stats,
)
from bot.controllers.record import (
    create_record,
    get_mvp,
    get_record,
    get_remained_players_in_game,
    increase_player_buy_in,
    update_net_profit_and_roi,
    update_record,
)
from bot.controllers.user import (
    get_all_users,
    get_last_played_users,
    get_non_admin_users,
    get_players_from_game,
    get_unplayed_users,
    get_user_from_db_by_tg_id,
)
from bot.internal.admin_menu import build_admin_menu
from bot.internal.callbacks import (
    AbortDialogCbData,
    AddFundsOperationType,
    CancelCbData,
    CustomFundsConfirmCbData,
    DeletePlayerCancelCbData,
    DeletePlayerConfirmCbData,
    DeletePlayerPageCbData,
    DeletePlayerProceedCbData,
    DeletePlayerSelectCbData,
    FinishGameCbData,
    GameMenuCbData,
    GameModeCbData,
    MultiselectFurtherCbData,
    PlayerCbData,
    SinglePlayerActionCbData,
)
from bot.internal.context import (
    Amount,
    FinalGameAction,
    GameAction,
    GameStatus,
    KeyboardMode,
    OperationType,
    RecordUpdateMode,
    SinglePlayerActionType,
    States,
)
from bot.internal.keyboards import (
    choose_single_player_kb,
    confirmation_dialog_kb,
    delete_player_confirm_kb,
    delete_player_list_kb,
    delete_player_summary_kb,
    finish_game_kb,
    game_menu_kb,
    mode_selector_kb,
    next_game_menu_kb,
    select_ratio_kb,
    skip_photo_kb,
    users_multiselect_kb,
)
from bot.internal.lexicon import buttons, texts
from bot.internal.notify_admin import send_message_to_player
from bot.services.game_finalization import finalize_game
from bot.services.photo_reminder import (
    cancel_photo_reminder,
    game_has_photo,
    schedule_photo_reminder,
    set_photo_warning,
)
from database.models import Debt, Game, Record, User

router = Router()
logger = getLogger(__name__)

MAX_INLINE_BUTTONS = 100
PAGINATED_PAGE_SIZE = 98


def _paginate_players(players: list[User], page: int) -> tuple[list[User], int, int]:
    total = len(players)
    if total <= MAX_INLINE_BUTTONS:
        return players, 1, 0
    total_pages = max(1, math.ceil(total / PAGINATED_PAGE_SIZE))
    page = max(0, min(page, total_pages - 1))
    start = page * PAGINATED_PAGE_SIZE
    end = start + PAGINATED_PAGE_SIZE
    return players[start:end], total_pages, page


async def _edit_or_answer(message, text: str, reply_markup=None) -> None:
    try:
        await message.edit_text(text=text, reply_markup=reply_markup)
    except TelegramBadRequest:
        await message.answer(text=text, reply_markup=reply_markup)


async def _get_bot_id(bot) -> int:
    bot_id = getattr(bot, "id", None)
    if bot_id:
        return bot_id
    cached = getattr(bot, "_cached_id", None)
    if cached:
        return cached
    me = await bot.get_me()
    bot._cached_id = me.id
    return me.id


def _filter_users(users: list[User], exclude_ids: set[int]) -> list[User]:
    return [user for user in users if user.id not in exclude_ids]


def _filter_ids(values: list[int], exclude_id: int) -> list[int]:
    return [value for value in values if value != exclude_id]


def _format_game_date(created_at) -> str:
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    return created_at.astimezone(settings.bot.TIMEZONE).strftime("%d.%m.%Y")


def _format_debt_lines(debts: list[Debt], direction: str) -> list[str]:
    lines: list[str] = []
    for debt in debts:
        amount = calculate_debt_amount(debt.amount, debt.game.ratio)
        amount_str = f"{amount:.2f}"
        game_date = _format_game_date(debt.game.created_at)
        if direction == "owes":
            counterparty = html.escape(debt.creditor.fullname)
            lines.append(
                f"• Game {debt.game_id:02d} ({game_date}): "
                f"<b>{amount_str} GEL</b> → {counterparty}"
            )
        else:
            counterparty = html.escape(debt.debtor.fullname)
            lines.append(
                f"• Game {debt.game_id:02d} ({game_date}): "
                f"<b>{amount_str} GEL</b> ← {counterparty}"
            )
    return lines


def _build_delete_summary(
    player: User,
    debts_as_debtor: list[Debt],
    debts_as_creditor: list[Debt],
) -> tuple[str, bool]:
    lines = [texts["admin_delete_player_summary_header"].format(html.escape(player.fullname))]
    has_debts = bool(debts_as_debtor or debts_as_creditor)
    lines.append("")
    if not has_debts:
        lines.append(texts["admin_delete_player_summary_no_debts"])
        return "\n".join(lines), False
    lines.append(texts["admin_delete_player_summary_debts_header"])
    if debts_as_debtor:
        lines.append(texts["admin_delete_player_summary_owes"])
        lines.extend(_format_debt_lines(debts_as_debtor, "owes"))
    if debts_as_creditor:
        lines.append(texts["admin_delete_player_summary_owed"])
        lines.extend(_format_debt_lines(debts_as_creditor, "owed"))
    return "\n".join(lines), True


def _is_unpaid(debt: Debt) -> bool:
    return (debt.is_paid is False) or (debt.paid_at is None)


def _collect_counterparty_lines(
    player: User, debts: list[Debt]
) -> dict[int, list[str]]:
    counterparty_lines: dict[int, list[str]] = {}
    for debt in debts:
        amount = calculate_debt_amount(debt.amount, debt.game.ratio)
        amount_str = f"{amount:.2f}"
        game_date = _format_game_date(debt.game.created_at)
        if debt.debtor_id == player.id:
            recipient_id = debt.creditor_id
            line = (
                f"• Game {debt.game_id:02d} ({game_date}): "
                f"<b>{amount_str} GEL</b> — "
                f"{html.escape(player.fullname)} owed you."
            )
        else:
            recipient_id = debt.debtor_id
            line = (
                f"• Game {debt.game_id:02d} ({game_date}): "
                f"<b>{amount_str} GEL</b> — "
                f"you owed {html.escape(player.fullname)}."
            )
        counterparty_lines.setdefault(recipient_id, []).append(line)
    return counterparty_lines


def _player_in_active_game(active_game: Game | None, player_id: int) -> bool:
    if not active_game:
        return False
    if active_game.host_id == player_id:
        return True
    return any(record.user_id == player_id for record in active_game.records)


async def _calculate_total_pot(game_id: int, db_session: AsyncSession) -> int:
    total_query = select(func.coalesce(func.sum(Record.buy_in), 0)).where(
        Record.game_id == game_id
    )
    result = await db_session.execute(total_query)
    return result.scalar_one()


async def _kick_from_group(bot, user_id: int) -> str:
    try:
        await bot.ban_chat_member(
            chat_id=settings.bot.GROUP_ID,
            user_id=user_id,
            revoke_messages=False,
        )
        await bot.unban_chat_member(
            chat_id=settings.bot.GROUP_ID,
            user_id=user_id,
            only_if_banned=True,
        )
        return "success"
    except TelegramForbiddenError as exc:
        logger.warning("Group removal forbidden for user %s: %s", user_id, exc)
        return f"forbidden ({exc})"
    except TelegramBadRequest as exc:
        logger.warning("Group removal failed for user %s: %s", user_id, exc)
        return f"failed ({exc})"
    except Exception as exc:
        logger.exception("Group removal unexpected failure for user %s", user_id)
        return f"failed ({exc})"


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
        callback_data.mode, callback_data.player_id, callback.from_user.id
    )
    match callback_data.mode:
        case SinglePlayerActionType.CHOOSE_HOST:
            active_game = await get_active_game(db_session)
            if active_game:
                logger.warning("Attempt to create game while game %s is active", active_game.id)
                await callback.message.answer(text=texts["game_already_active"])
                return

            await state.update_data(next_game_host_id=callback_data.player_id)
            all_users = _filter_users(await get_all_users(db_session), {bot_id})
            last_played_users = _filter_ids(
                await get_last_played_users(db_session), bot_id
            )
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
            player = await get_user_from_db_by_tg_id(
                callback_data.player_id, db_session
            )
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
                text=texts["custom_funds_amount_prompt"].format(player.fullname),
            )
            await state.set_state(States.ENTER_CUSTOM_FUNDS)
        case SinglePlayerActionType.SET_BUY_OUT:
            await state.update_data(
                player_id=callback_data.player_id, game_id=callback_data.game_id
            )
            player = await get_user_from_db_by_tg_id(
                callback_data.player_id, db_session
            )
            await _edit_or_answer(
                callback.message,
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
    bot_id = await _get_bot_id(callback.bot)
    if callback_data.player_id == bot_id:
        return
    data = await state.get_data()
    match callback_data.mode:
        case KeyboardMode.NEW_GAME:
            users = await get_all_users(db_session)
            chosen_users = _filter_ids(
                data.get("chosen_for_new_game", list()), bot_id
            )
        case KeyboardMode.ADD_PLAYERS:
            users = await get_unplayed_users(db_session)
            chosen_users = _filter_ids(
                data.get("chosen_for_add_players", list()), bot_id
            )
        case KeyboardMode.PLAYERS_ADD_1000:
            users = await get_players_from_game(callback_data.game_id, db_session)
            chosen_users = _filter_ids(
                data.get("chosen_for_add_1000", list()), bot_id
            )
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
            players_not_in_game = _filter_users(
                await get_unplayed_users(db_session), {bot_id}
            )
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
                await state.update_data(next_game_yearly_stats=True)
                await _edit_or_answer(
                    callback.message,
                    text=texts["yearly_stats_set"],
                    reply_markup=game_menu_kb(
                        GameStatus.ACTIVE if await get_active_game(db_session) else None,
                        is_admin=user.is_admin,
                    ),
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
                await callback.message.answer(
                    text=texts["admin_delete_player_no_players"]
                )
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


@router.callback_query(DeletePlayerPageCbData.filter())
async def delete_player_page_handler(
    callback: CallbackQuery,
    callback_data: DeletePlayerPageCbData,
    user: User,
    db_session: AsyncSession,
) -> None:
    await callback.answer()
    if not user.is_admin:
        await callback.message.answer(text=texts["insufficient_privileges"])
        return
    bot_id = await _get_bot_id(callback.bot)
    players = await get_non_admin_users(
        db_session,
        exclude_ids={callback.from_user.id, bot_id},
    )
    if not players:
        await callback.message.answer(text=texts["admin_delete_player_no_players"])
        return
    page_players, total_pages, page = _paginate_players(players, callback_data.page)
    try:
        await callback.message.edit_reply_markup(
            reply_markup=delete_player_list_kb(
                players=page_players,
                page=page,
                total_pages=total_pages,
            )
        )
    except TelegramBadRequest:
        await callback.message.answer(
            text=texts["admin_delete_player_dialog"],
            reply_markup=delete_player_list_kb(
                players=page_players,
                page=page,
                total_pages=total_pages,
            ),
        )


@router.callback_query(DeletePlayerCancelCbData.filter())
async def delete_player_cancel_handler(
    callback: CallbackQuery,
    callback_data: DeletePlayerCancelCbData,
    user: User,
    db_session: AsyncSession,
) -> None:
    await callback.answer()
    if not user.is_admin:
        await callback.message.answer(text=texts["insufficient_privileges"])
        return
    bot_id = await _get_bot_id(callback.bot)
    players = await get_non_admin_users(
        db_session,
        exclude_ids={callback.from_user.id, bot_id},
    )
    if not players:
        await callback.message.answer(text=texts["admin_delete_player_no_players"])
        return
    page_players, total_pages, page = _paginate_players(players, callback_data.page)
    await _edit_or_answer(
        callback.message,
        text=texts["admin_delete_player_dialog"],
        reply_markup=delete_player_list_kb(
            players=page_players,
            page=page,
            total_pages=total_pages,
        ),
    )


@router.callback_query(DeletePlayerSelectCbData.filter())
async def delete_player_select_handler(
    callback: CallbackQuery,
    callback_data: DeletePlayerSelectCbData,
    user: User,
    db_session: AsyncSession,
) -> None:
    await callback.answer()
    if not user.is_admin:
        await callback.message.answer(text=texts["insufficient_privileges"])
        return
    bot_id = await _get_bot_id(callback.bot)
    player = await get_user_from_db_by_tg_id(callback_data.user_id, db_session)
    if player is None:
        await callback.message.answer(text=texts["admin_delete_player_no_players"])
        return
    if player.id == bot_id:
        await callback.message.answer(text=texts["admin_delete_player_blocked_bot"])
        return
    if player.is_admin or player.id == callback.from_user.id:
        await callback.message.answer(text=texts["admin_delete_player_blocked_admin"])
        return
    active_game = await get_active_game(db_session)
    if _player_in_active_game(active_game, player.id):
        await callback.message.answer(
            text=texts["admin_delete_player_blocked_active_game"].format(
                html.escape(player.fullname),
                active_game.id,
            )
        )
        return

    debts_as_debtor = await get_unpaid_debts_as_debtor(player.id, db_session)
    debts_as_creditor = await get_unpaid_debts_as_creditor(player.id, db_session)
    summary_text, has_debts = _build_delete_summary(
        player,
        debts_as_debtor,
        debts_as_creditor,
    )
    await _edit_or_answer(
        callback.message,
        text=summary_text,
        reply_markup=delete_player_summary_kb(
            user_id=player.id,
            page=callback_data.page,
            has_debts=has_debts,
        ),
    )


@router.callback_query(DeletePlayerProceedCbData.filter())
async def delete_player_proceed_handler(
    callback: CallbackQuery,
    callback_data: DeletePlayerProceedCbData,
    user: User,
    db_session: AsyncSession,
) -> None:
    await callback.answer()
    if not user.is_admin:
        await callback.message.answer(text=texts["insufficient_privileges"])
        return
    bot_id = await _get_bot_id(callback.bot)
    player = await get_user_from_db_by_tg_id(callback_data.user_id, db_session)
    if player is None:
        await callback.message.answer(text=texts["admin_delete_player_no_players"])
        return
    if player.id == bot_id:
        await callback.message.answer(text=texts["admin_delete_player_blocked_bot"])
        return
    confirm_text = texts["admin_delete_player_confirm"].format(
        html.escape(player.fullname)
    )
    await _edit_or_answer(
        callback.message,
        text=confirm_text,
        reply_markup=delete_player_confirm_kb(
            user_id=player.id,
            page=callback_data.page,
            force=callback_data.force,
        ),
    )


@router.callback_query(DeletePlayerConfirmCbData.filter())
async def delete_player_confirm_handler(
    callback: CallbackQuery,
    callback_data: DeletePlayerConfirmCbData,
    user: User,
    db_session: AsyncSession,
) -> None:
    await callback.answer()
    if not user.is_admin:
        await callback.message.answer(text=texts["insufficient_privileges"])
        return
    bot_id = await _get_bot_id(callback.bot)
    player = await get_user_from_db_by_tg_id(callback_data.user_id, db_session)
    if player is None:
        await callback.message.answer(text=texts["admin_delete_player_no_players"])
        return
    if player.id == bot_id:
        await callback.message.answer(text=texts["admin_delete_player_blocked_bot"])
        return
    if player.is_admin or player.id == callback.from_user.id:
        await callback.message.answer(text=texts["admin_delete_player_blocked_admin"])
        return
    active_game = await get_active_game(db_session)
    if _player_in_active_game(active_game, player.id):
        await callback.message.answer(
            text=texts["admin_delete_player_blocked_active_game"].format(
                html.escape(player.fullname),
                active_game.id,
            )
        )
        return

    player_name = player.fullname
    player_id = player.id
    admin_id = callback.from_user.id

    debts_query = (
        select(Debt)
        .where((Debt.debtor_id == player_id) | (Debt.creditor_id == player_id))
        .options(
            selectinload(Debt.creditor),
            selectinload(Debt.debtor),
            selectinload(Debt.game),
        )
    )
    debts_result = await db_session.execute(debts_query)
    debts_all = list(debts_result.unique().scalars().all())
    debts_unpaid = [debt for debt in debts_all if _is_unpaid(debt)]
    debts_unpaid_as_debtor = [
        debt for debt in debts_unpaid if debt.debtor_id == player_id
    ]
    debts_unpaid_as_creditor = [
        debt for debt in debts_unpaid if debt.creditor_id == player_id
    ]
    counterparty_lines = _collect_counterparty_lines(player, debts_unpaid)
    counterparty_names: dict[int, str] = {}
    for debt in debts_unpaid:
        if debt.creditor:
            counterparty_names[debt.creditor_id] = debt.creditor.fullname
        if debt.debtor:
            counterparty_names[debt.debtor_id] = debt.debtor.fullname
    for debt in debts_all:
        amount = calculate_debt_amount(debt.amount, debt.game.ratio)
        logger.info(
            "Delete player debt removed: admin_id=%s user_id=%s debt_id=%s game_id=%s "
            "debtor_id=%s creditor_id=%s amount=%s paid=%s",
            admin_id,
            player_id,
            debt.id,
            debt.game_id,
            debt.debtor_id,
            debt.creditor_id,
            f"{amount:.2f}",
            debt.is_paid,
        )

    records_count_result = await db_session.execute(
        select(func.count()).select_from(Record).where(Record.user_id == player_id)
    )
    records_count = records_count_result.scalar_one()

    record_games_result = await db_session.execute(
        select(Record.game_id).where(Record.user_id == player_id)
    )
    record_game_ids = sorted(set(record_games_result.scalars().all()))

    host_games_result = await db_session.execute(
        select(Game.id).where(Game.host_id == player_id)
    )
    host_game_ids = [row[0] for row in host_games_result.all()]

    mvp_games_result = await db_session.execute(
        select(Game.id).where(Game.mvp_id == player_id)
    )
    mvp_game_ids = [row[0] for row in mvp_games_result.all()]

    await db_session.execute(
        delete(Debt).where((Debt.debtor_id == player_id) | (Debt.creditor_id == player_id))
    )
    await db_session.execute(delete(Record).where(Record.user_id == player_id))

    if host_game_ids:
        await db_session.execute(
            update(Game)
            .where(Game.host_id == player_id)
            .values(host_id=Game.admin_id)
        )

    recalc_game_ids = sorted(set(record_game_ids) | set(mvp_game_ids))
    for game_id in recalc_game_ids:
        await update_net_profit_and_roi(game_id, db_session)
        total_pot = await _calculate_total_pot(game_id, db_session)
        await db_session.execute(
            update(Game).where(Game.id == game_id).values(total_pot=total_pot)
        )

    for game_id in mvp_game_ids:
        new_mvp_id = await get_mvp(game_id, db_session)
        await db_session.execute(
            update(Game).where(Game.id == game_id).values(mvp_id=new_mvp_id)
        )
        logger.info(
            "Delete player MVP recalculated: admin_id=%s game_id=%s old_mvp=%s new_mvp=%s",
            admin_id,
            game_id,
            player_id,
            new_mvp_id,
        )

    await db_session.delete(player)
    await db_session.flush()

    logger.info(
        "Player deleted: admin_id=%s user_id=%s debts_removed=%s records_removed=%s "
        "host_reassigned_games=%s total_pot_recalc_games=%s",
        admin_id,
        player_id,
        len(debts_all),
        records_count,
        host_game_ids,
        recalc_game_ids,
    )
    await db_session.commit()

    try:
        group_result = await _kick_from_group(callback.bot, player_id)
    except Exception as exc:
        logger.exception("Failed to remove user %s from group", player_id)
        group_result = f"failed ({exc})"
    for recipient_id, lines in counterparty_lines.items():
        if recipient_id == player_id:
            continue
        recipient_name = counterparty_names.get(recipient_id, "player")
        notification = "\n".join(
            [
                texts["delete_player_notify_header"],
                texts["delete_player_notify_body"].format(html.escape(player_name)),
                "",
                texts["delete_player_notify_details_header"],
                *lines,
            ]
        )
        try:
            await send_message_to_player(
                callback.bot,
                user_id=recipient_id,
                fullname=recipient_name,
                text=notification,
                disable_web_page_preview=True,
            )
        except Exception:
            logger.exception("Failed to notify user %s about player removal", recipient_id)

    summary_text, _ = _build_delete_summary(
        player,
        debts_unpaid_as_debtor,
        debts_unpaid_as_creditor,
    )
    report_lines = [
        texts["admin_delete_player_report_header"],
        summary_text,
        "",
        texts["admin_delete_player_report_results"],
        texts["admin_delete_player_report_debts"].format(len(debts_all)),
        texts["admin_delete_player_report_records"].format(records_count),
    ]
    if host_game_ids:
        report_lines.append(
            texts["admin_delete_player_report_host"].format(
                ", ".join(f"{game_id:02d}" for game_id in host_game_ids)
            )
        )
    if mvp_game_ids:
        report_lines.append(
            texts["admin_delete_player_report_mvp"].format(
                ", ".join(f"{game_id:02d}" for game_id in mvp_game_ids)
            )
        )
    if recalc_game_ids:
        report_lines.append(
            texts["admin_delete_player_report_pot"].format(
                ", ".join(f"{game_id:02d}" for game_id in recalc_game_ids)
            )
        )
    report_lines.append(
        texts["admin_delete_player_group_result"].format(
            html.escape(group_result)
        )
    )
    try:
        await send_message_to_player(
            callback.bot,
            user_id=admin_id,
            fullname=user.fullname,
            text="\n".join(report_lines),
            disable_web_page_preview=True,
        )
    except Exception:
        logger.exception("Failed to send admin report for deleted user %s", player_id)
    with suppress(TelegramBadRequest):
        await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer(texts["admin_delete_player_done_popup"])


@router.callback_query(GameModeCbData.filter())
async def game_mode_handler(
    callback: CallbackQuery,
    callback_data: GameModeCbData,
    state: FSMContext,
) -> None:
    await callback.answer()
    await state.update_data(next_game_ratio=callback_data.ratio)
    await callback.message.answer(text=texts["ratio_set"].format(callback_data.ratio))


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
            text=texts["custom_funds_amount_prompt"].format(player.fullname),
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
        text=texts["custom_funds_applied"].format(game_id, amount, player.fullname, buy_in)
    )


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
            chosen_users = _filter_ids(
                data.get("chosen_for_new_game", list()),
                bot_id,
            )
            await callback.bot.send_message(
                chat_id=settings.bot.GROUP_ID,
                text=texts["game_started_group"].format(
                    game_id=game.id,
                    players_count=len(chosen_users),
                    host_name=host.fullname if host else "Unknown",
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
            logger.info("Game %s: %d players added to new game", game.id, len(chosen_users))
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
            raise ValueError("Unexpected mode")
    await callback.message.answer(text=text)


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


@router.callback_query(AbortDialogCbData.filter())
async def abort_game_handler(
    callback: CallbackQuery,
    callback_data: AbortDialogCbData,
    db_session: AsyncSession,
) -> None:
    await callback.answer()
    logger.info("Game %s aborted by user %s", callback_data.game_id, callback.from_user.id)
    cancel_photo_reminder(callback_data.game_id)
    await abort_game(callback_data.game_id, db_session)
    players: list[User] = await get_players_from_game(callback_data.game_id, db_session)
    for player in players:
        player.games_played -= 1
        db_session.add(player)
    await callback.message.answer(
        text=texts["abort_game_reply"].format(callback_data.game_id)
    )


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
    logger.debug("FinishGame: action=%s game_id=%s user_id=%s",
        callback_data.action, callback_data.game_id, callback.from_user.id)
    bot_id = await _get_bot_id(callback.bot)
    match callback_data.action:
        case FinalGameAction.ADD_PLAYERS_WITH_0:
            active_players = await get_players_from_game(
                callback_data.game_id, db_session
            )
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
                logger.warning("Game %s: finalization blocked, %d players without buy-out",
                    callback_data.game_id, remained_players)
                await callback.message.answer(
                    texts["remained_players"].format(
                        callback_data.game_id, remained_players
                    )
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
                logger.warning("Game %s: finalization blocked, %d players without buy-out",
                    callback_data.game_id, remained_players)
                await callback.message.answer(
                    texts["remained_players"].format(
                        callback_data.game_id, remained_players
                    )
                )
            else:
                await _do_finalize(callback, callback_data.game_id, state, db_session)
