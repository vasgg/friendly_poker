from contextlib import suppress
from datetime import datetime
import logging

from aiogram import Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.controllers.debt import (
    calculate_debt_amount,
    get_debt_by_id,
    get_unpaid_debts_as_creditor,
    get_unpaid_debts_as_debtor,
)
from bot.controllers.game import get_game_by_id
from bot.controllers.user import get_user_from_db_by_tg_id
from bot.internal.notify_admin import send_message_to_player
from bot.internal.callbacks import DebtActionCbData, DebtStatsCbData
from bot.internal.lexicon import texts
from bot.internal.context import DebtAction, DebtStatsView
from bot.internal.keyboards import get_paid_button_confirmation
from database.models import User

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(DebtActionCbData.filter())
async def debt_handler(
    callback: CallbackQuery,
    callback_data: DebtActionCbData,
    db_session: AsyncSession,
) -> None:
    logger.info(
        "Debt action: debt_id=%s action=%s user_id=%s",
        callback_data.debt_id,
        callback_data.action,
        callback.from_user.id,
    )
    await callback.answer()
    debt = await get_debt_by_id(callback_data.debt_id, db_session)
    if debt is None:
        logger.warning("Debt not found: debt_id=%s", callback_data.debt_id)
        return
    game = await get_game_by_id(debt.game_id, db_session)
    if game is None:
        logger.warning("Game not found: game_id=%s", debt.game_id)
        return
    creditor: User = await get_user_from_db_by_tg_id(debt.creditor_id, db_session)
    debtor: User = await get_user_from_db_by_tg_id(debt.debtor_id, db_session)
    if creditor is None or debtor is None:
        logger.warning("Creditor or debtor not found for debt_id=%s", callback_data.debt_id)
        return
    debtor_username = "@" + debtor.username if debtor.username else debtor.fullname
    creditor_username = (
        "@" + creditor.username if creditor.username else creditor.fullname
    )
    amount = calculate_debt_amount(debt.amount, game.ratio)
    match callback_data.action:
        case DebtAction.MARK_AS_PAID:
            try:
                await callback.message.edit_reply_markup()
            except TelegramBadRequest:
                await callback.message.answer(
                    texts["debt_marked_as_paid_confirmation"].format(
                        debt.game_id, debt.id, amount, creditor_username
                    )
                )
            await send_message_to_player(
                callback.bot,
                user_id=creditor.id,
                fullname=creditor.fullname,
                text=texts["debt_marked_as_paid"].format(
                    debt.game_id, debt.id, debtor_username, amount
                ),
                reply_markup=await get_paid_button_confirmation(debt.id, creditor.id),
            )
            debt.is_paid = True
            db_session.add(debt)
            await db_session.flush()
            logger.info("Debt %s marked as paid by debtor %s", debt.id, debtor.id)
        case DebtAction.MARK_AS_UNPAID:
            logger.info("Debt %s mark as unpaid action (not implemented)", debt.id)
        case DebtAction.COMPLETE_DEBT:
            try:
                await callback.message.delete()
            except TelegramBadRequest:
                await callback.message.answer(
                    texts["debt_complete_confirmation"].format(
                        debt.game_id, debt.id, amount, debtor_username
                    )
                )
            debt.is_paid = True
            debt.paid_at = datetime.now(settings.bot.TIMEZONE)
            db_session.add(debt)
            await db_session.flush()

            await send_message_to_player(
                callback.bot,
                user_id=debtor.id,
                fullname=debtor.fullname,
                text=texts["debt_complete"].format(
                    debt.game_id, debt.id, creditor_username, amount
                ),
            )
            with suppress(TelegramBadRequest):
                await callback.bot.delete_message(
                    chat_id=debtor.id, message_id=debt.debt_message_id
                )
            logger.info("Debt %s completed by creditor %s", debt.id, creditor.id)


@router.callback_query(DebtStatsCbData.filter())
async def debt_stats_handler(
    callback: CallbackQuery,
    callback_data: DebtStatsCbData,
    user: User,
    db_session: AsyncSession,
) -> None:
    await callback.answer()
    logger.info("Debt stats view: view=%s user_id=%s", callback_data.view, user.id)

    if callback_data.view == DebtStatsView.I_OWE:
        debts = await get_unpaid_debts_as_debtor(user.id, db_session)
        if not debts:
            return
        response = texts["stats_debt_detail_header"]
        response += texts["stats_debt_detail_i_owe"]
        for debt in debts:
            amount = calculate_debt_amount(debt.amount, debt.game.ratio)
            creditor_name = debt.creditor.fullname
            response += texts["stats_debt_line"].format(
                debt.game_id, amount, creditor_name
            )
    else:
        debts = await get_unpaid_debts_as_creditor(user.id, db_session)
        if not debts:
            return
        response = texts["stats_debt_detail_header"]
        response += texts["stats_debt_detail_owe_me"]
        for debt in debts:
            amount = calculate_debt_amount(debt.amount, debt.game.ratio)
            debtor_name = debt.debtor.fullname
            response += texts["stats_debt_line"].format(
                debt.game_id, amount, debtor_name
            )

    await callback.message.answer(response)
