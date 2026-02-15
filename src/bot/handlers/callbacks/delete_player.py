import html
from contextlib import suppress
from datetime import UTC
from logging import getLogger

from aiogram import Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
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
from bot.controllers.game import get_active_game
from bot.controllers.record import get_mvp, update_net_profit_and_roi
from bot.controllers.user import get_non_admin_users, get_user_from_db_by_tg_id
from bot.handlers.callbacks.common import _edit_or_answer, _get_bot_id, _paginate_players
from bot.internal.callbacks import (
    DeletePlayerCancelCbData,
    DeletePlayerConfirmCbData,
    DeletePlayerPageCbData,
    DeletePlayerProceedCbData,
    DeletePlayerSelectCbData,
)
from bot.internal.keyboards import (
    delete_player_confirm_kb,
    delete_player_list_kb,
    delete_player_summary_kb,
)
from bot.internal.lexicon import texts
from bot.internal.notify_admin import send_message_to_player
from database.models import Debt, Game, Record, User

router = Router()
logger = getLogger(__name__)


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
    lines = [
        texts["admin_delete_player_summary_header"].format(html.escape(player.fullname))
    ]
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


def _collect_counterparty_lines(player: User, debts: list[Debt]) -> dict[int, list[str]]:
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
    except TelegramForbiddenError as exc:
        logger.warning("Group removal forbidden for user %s: %s", user_id, exc)
        return f"forbidden ({exc})"
    except TelegramBadRequest as exc:
        logger.warning("Group removal failed for user %s: %s", user_id, exc)
        return f"failed ({exc})"
    except Exception as exc:
        logger.exception("Group removal unexpected failure for user %s", user_id)
        return f"failed ({exc})"
    else:
        return "success"


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
    confirm_text = texts["admin_delete_player_confirm"].format(html.escape(player.fullname))
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
    debts_unpaid_as_debtor = [debt for debt in debts_unpaid if debt.debtor_id == player_id]
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

    record_games_result = await db_session.execute(select(Record.game_id).where(Record.user_id == player_id))
    record_game_ids = sorted(set(record_games_result.scalars().all()))

    host_games_result = await db_session.execute(select(Game.id).where(Game.host_id == player_id))
    host_game_ids = [row[0] for row in host_games_result.all()]

    mvp_games_result = await db_session.execute(select(Game.id).where(Game.mvp_id == player_id))
    mvp_game_ids = [row[0] for row in mvp_games_result.all()]

    await db_session.execute(
        delete(Debt).where((Debt.debtor_id == player_id) | (Debt.creditor_id == player_id))
    )
    await db_session.execute(delete(Record).where(Record.user_id == player_id))

    if host_game_ids:
        await db_session.execute(
            update(Game).where(Game.host_id == player_id).values(host_id=Game.admin_id)
        )

    recalc_game_ids = sorted(set(record_game_ids) | set(mvp_game_ids))
    for game_id in recalc_game_ids:
        await update_net_profit_and_roi(game_id, db_session)
        total_pot = await _calculate_total_pot(game_id, db_session)
        await db_session.execute(update(Game).where(Game.id == game_id).values(total_pot=total_pot))

    for game_id in mvp_game_ids:
        new_mvp_id = await get_mvp(game_id, db_session)
        await db_session.execute(update(Game).where(Game.id == game_id).values(mvp_id=new_mvp_id))
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
            logger.exception(
                "Failed to notify user %s about player removal", recipient_id
            )

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
        texts["admin_delete_player_group_result"].format(html.escape(group_result))
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
