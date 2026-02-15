import html
from contextlib import suppress
from logging import getLogger

from aiogram import Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.controllers.debt import get_unpaid_debts_as_creditor, get_unpaid_debts_as_debtor
from bot.controllers.game import get_active_game
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
from bot.services.player_deletion import (
    build_delete_summary,
    delete_player_from_db,
    player_in_active_game,
)
from database.models import User

router = Router()
logger = getLogger(__name__)


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
    players.sort(key=lambda player: (player.games_played, player.fullname.casefold()))
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
    players.sort(key=lambda player: (player.games_played, player.fullname.casefold()))
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
    if player_in_active_game(active_game, player.id):
        await callback.message.answer(
            text=texts["admin_delete_player_blocked_active_game"].format(
                html.escape(player.fullname),
                active_game.id,
            )
        )
        return

    debts_as_debtor = await get_unpaid_debts_as_debtor(player.id, db_session)
    debts_as_creditor = await get_unpaid_debts_as_creditor(player.id, db_session)
    summary_text, has_debts = build_delete_summary(
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
    if player_in_active_game(active_game, player.id):
        await callback.message.answer(
            text=texts["admin_delete_player_blocked_active_game"].format(
                html.escape(player.fullname),
                active_game.id,
            )
        )
        return

    admin_id = callback.from_user.id
    result = await delete_player_from_db(player, admin_id, db_session)
    await db_session.commit()

    try:
        group_result = await _kick_from_group(callback.bot, result.player_id)
    except Exception as exc:
        logger.exception("Failed to remove user %s from group", result.player_id)
        group_result = f"failed ({exc})"
    for recipient_id, lines in result.counterparty_lines.items():
        if recipient_id == result.player_id:
            continue
        recipient_name = result.counterparty_names.get(recipient_id, "player")
        notification = "\n".join(
            [
                texts["delete_player_notify_header"],
                texts["delete_player_notify_body"].format(html.escape(result.player_name)),
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

    report_lines = [
        texts["admin_delete_player_report_header"],
        result.admin_summary_text,
        "",
        texts["admin_delete_player_report_results"],
        texts["admin_delete_player_report_debts"].format(result.debts_removed),
        texts["admin_delete_player_report_records"].format(result.records_removed),
    ]
    if result.host_reassigned_games:
        report_lines.append(
            texts["admin_delete_player_report_host"].format(
                ", ".join(f"{game_id:02d}" for game_id in result.host_reassigned_games)
            )
        )
    if result.mvp_recalculated_games:
        report_lines.append(
            texts["admin_delete_player_report_mvp"].format(
                ", ".join(f"{game_id:02d}" for game_id in result.mvp_recalculated_games)
            )
        )
    if result.pot_recalculated_games:
        report_lines.append(
            texts["admin_delete_player_report_pot"].format(
                ", ".join(f"{game_id:02d}" for game_id in result.pot_recalculated_games)
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
        logger.exception(
            "Failed to send admin report for deleted user %s", result.player_id
        )
    with suppress(TelegramBadRequest):
        await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer(texts["admin_delete_player_done_popup"])
