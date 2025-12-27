from contextlib import suppress
from datetime import datetime

from aiogram import Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.controllers.debt import calculate_debt_amount, get_debt_by_id
from bot.controllers.game import get_game_by_id
from bot.controllers.user import get_user_from_db_by_tg_id
from bot.internal.notify_admin import send_message_to_player
from bot.internal.callbacks import DebtActionCbData
from bot.internal.lexicon import texts
from bot.internal.context import DebtAction
from bot.internal.keyboards import get_paid_button_confirmation
from database.models import User

router = Router()


@router.callback_query(DebtActionCbData.filter())
async def debt_handler(
    callback: CallbackQuery,
    callback_data: DebtActionCbData,
    db_session: AsyncSession,
) -> None:
    await callback.answer()
    debt = await get_debt_by_id(callback_data.debt_id, db_session)
    game = await get_game_by_id(debt.game_id, db_session)
    creditor: User = await get_user_from_db_by_tg_id(debt.creditor_id, db_session)
    debtor: User = await get_user_from_db_by_tg_id(debt.debtor_id, db_session)
    debtor_username = "@" + debtor.username if debtor.username else debtor.fullname
    creditor_username = (
        "@" + creditor.username if creditor.username else creditor.fullname
    )
    amount = calculate_debt_amount(debt.amount, game.ratio)
    match callback_data.action:
        case DebtAction.MARK_AS_PAID:
            await callback.message.edit_reply_markup()
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
        case DebtAction.MARK_AS_UNPAID:
            ...
        case DebtAction.COMPLETE_DEBT:
            with suppress(TelegramBadRequest):
                await callback.message.delete()
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
