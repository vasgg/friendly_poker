from datetime import datetime

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.controllers.debt import get_debt_by_id
from bot.controllers.user import get_user_from_db_by_tg_id
from bot.internal.callbacks import DebtActionCbData
from bot.internal.dicts import texts
from bot.internal.context import DebtAction
from bot.internal.keyboards import get_paid_button_confirmation
from database.models import User

router = Router()


@router.callback_query(DebtActionCbData.filter())
async def debt_handler(
    callback: CallbackQuery,
    callback_data: DebtActionCbData,
    state: FSMContext,
    db_session: AsyncSession,
) -> None:
    await callback.answer()
    debt = await get_debt_by_id(callback_data.debt_id, db_session)
    creditor: User = await get_user_from_db_by_tg_id(debt.creditor_id, db_session)
    debtor: User = await get_user_from_db_by_tg_id(debt.debtor_id, db_session)
    debtor_username = "@" + debtor.username if debtor.username else debtor.fullname
    creditor_username = "@" + creditor.username if creditor.username else creditor.fullname
    match callback_data.action:
        case DebtAction.MARK_AS_PAID:
            await callback.bot.send_message(
                chat_id=creditor.id,
                text=texts["debt_marked_as_paid"].format(
                    debt.game_id, debt.id, debtor_username, debt.amount / 100
                ),
                reply_markup=await get_paid_button_confirmation(debt.id, creditor.id),
            )
            debt.is_paid = True
            # debt.debt_message_id = paid_message.message_id
            db_session.add(debt)
            await db_session.flush()
            # data = {
            #     f"debt{debt.id}_paid_message_id": paid_message.message_id,
            # }
            # await state.update_data(data)
        case DebtAction.MARK_AS_UNPAID:
            ...
        case DebtAction.COMPLETE_DEBT:
            debt.is_paid = True
            debt.paid_at = datetime.now(settings.bot.TIMEZONE)
            db_session.add(debt)
            await db_session.flush()

            await callback.bot.send_message(
                chat_id=debtor.id,
                text=texts["debt_complete"].format(debt.game_id, debt.id, creditor_username, debt.amount / 100),
            )
            # data = await state.get_data()
            # paid_message_id = data.get(f"debt{debt.id}_paid_message_id")
            # paid_message_chat_id = data.get(f"debt{debt.id}_paid_message_chat_id")
            await callback.bot.delete_message(
                chat_id=debtor.id, message_id=debt.debt_message_id
            )


# @router.callback_query(lambda c: c.data.Startswith("debt_"))
# async def debt_mark_us_paid(
#     callback: CallbackQuery, state: FSMContext, db_session: AsyncSession
# ):
#     await callback.answer()
#     debt_id = int(callback.data[5:])
#     debt = await get_debt_by_id(debt_id, db_session)
#     debt.is_paid = True
#     db_session.add(debt)
#     await db_session.flush()
#
#     creditor = await get_user_from_db_by_tg_id(debt.creditor_id, db_session)
#     debtor = await get_user_from_db_by_tg_id(debt.debtor_id, db_session)
#
#     debtor_username = "@" + debtor.username if debtor.username else debtor.fullname
#     paid_message = await callback.bot.send_message(
#         chat_id=creditor.id,
#         text=texts["debt_marked_as_paid"].format(
#             debt.game_id, debt.id, debtor_username, debt.amount / 100
#         ),
#         reply_markup=await get_paid_button_confirmation(debt.id),
#     )
#     await state.update_data(
#         **{f"debt{debt_id}_paid_message_id": paid_message.message_id}
#     )
#     await state.update_data(
#         **{f"debt{debt_id}_paid_message_chat_id": paid_message.chat.id}
#     )

#
# @router.callback_query(lambda c: c.data.endswith("_yeah_debt"))
# async def coplete_debt(
#     callback: CallbackQuery,
#     state: FSMContext,
#     db_session: AsyncSession,
# ):
#     await callback.answer()
#     debt_id = int(callback.data[:-10])
#     debt = await get_debt_by_id(debt_id, db_session)
#     debt.is_paid = True
#     debt.paid_at = datetime.now(settings.bot.TIMEZONE)
#     db_session.add(debt)
#     await db_session.flush()
#
#     creditor = await get_user_from_db_by_tg_id(debt.creditor_id, db_session)
#     debtor = await get_user_from_db_by_tg_id(debt.debtor_id, db_session)
#     creditor_username = (
#         "@" + creditor.username if creditor.username else creditor.fullname
#     )
#     await callback.bot.send_message(
#         chat_id=debtor.id,
#         text=texts["debt_complete"].format(debt.game_id, debt.id, creditor_username),
#     )
#     data = await state.get_data()
#     paid_message_id = data.get(f"debt{debt_id}_paid_message_id")
#     paid_message_chat_id = data.get(f"debt{debt_id}_paid_message_chat_id")
#     await callback.bot.delete_message(
#         chat_id=paid_message_chat_id, message_id=paid_message_id
#     )


@router.callback_query(lambda c: c.data.endswith("_nope_debt"))
async def incoplete_debt(callback: CallbackQuery, db_session: AsyncSession):
    await callback.answer()
    debt_id = int(callback.data[:-10])
    debt = await get_debt_by_id(debt_id, db_session)
    debt.is_paid = False
    debt.paid_at = None
    db_session.add(debt)
    await db_session.flush()

    creditor = await get_user_from_db_by_tg_id(debt.creditor_id, db_session)
    creditor_username = (
        "@" + creditor.username if creditor.username else creditor.fullname
    )
    debtor = await get_user_from_db_by_tg_id(debt.debtor_id, db_session)
    await callback.bot.send_message(
        chat_id=debtor.id,
        text=texts["debt_incomplete"].format(debt.game_id, debt.id, creditor_username),
    )
