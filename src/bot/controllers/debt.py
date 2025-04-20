from datetime import datetime
import heapq

from aiogram.types import CallbackQuery
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.controllers.user import get_user_from_db_by_tg_id
from bot.internal.dicts import texts
from bot.internal.keyboards import get_paid_button
from database.models import Debt, User



async def get_debts(game_id, db_session):
    debts = select(Debt).filter(Debt.game_id == game_id)
    result = await db_session.execute(debts)
    debts = result.unique().scalars().all()
    return debts

async def equalizer(debtors: list[tuple[int, int]], creditors: list[tuple[int, int]], game_id: int) -> list[Debt]:
    transactions = []

    debtors_heap = [(abs(amount), user_id) for amount, user_id in debtors]
    heapq.heapify(debtors_heap)

    creditors_heap = [(-amount, user_id) for amount, user_id in creditors]
    heapq.heapify(creditors_heap)

    while debtors_heap and creditors_heap:
        debt_amount, debtor_id = heapq.heappop(debtors_heap)
        credit_amount_neg, creditor_id = heapq.heappop(creditors_heap)

        credit_amount = -credit_amount_neg
        amount_to_transfer = min(debt_amount, credit_amount)

        transactions.append(
            Debt(
                game_id=game_id,
                creditor_id=creditor_id,
                debtor_id=debtor_id,
                amount=amount_to_transfer,
            )
        )

        remaining_debt = debt_amount - amount_to_transfer
        remaining_credit = credit_amount - amount_to_transfer

        if remaining_debt > 0:
            heapq.heappush(debtors_heap, (remaining_debt, debtor_id))
        if remaining_credit > 0:
            heapq.heappush(creditors_heap, (-remaining_credit, creditor_id))

    return transactions


async def commit_debts_to_db(
    transactions: list[Debt], db_session: AsyncSession
) -> None:
    for transaction in transactions:
        db_session.add(transaction)
    await db_session.flush()


async def debt_informer_by_id(
    game_id: int, callback: CallbackQuery, db_session: AsyncSession
) -> None:
    debts = await get_debts(game_id, db_session)
    for debt in debts:
        creditor: User = await get_user_from_db_by_tg_id(debt.creditor_id, db_session)
        debtor: User = await get_user_from_db_by_tg_id(debt.debtor_id, db_session)
        creditor_username = (
            "@" + creditor.username if creditor.username else creditor.fullname
        )
        debtor_username = "@" + debtor.username if debtor.username else debtor.fullname
        await callback.bot.send_message(
            chat_id=debtor.id,
            text=texts["debtor_personal_game_report"].format(
                debt.game_id, debt.id, debt.amount / 100, creditor_username
            ),
            reply_markup=await get_paid_button(debt.id, debtor.id),
        )
        await callback.bot.send_message(
            chat_id=creditor.id,
            text=texts["creditor_personal_game_report"].format(
                debt.game_id, debt.id, debtor_username, debt.amount / 100
            ),
        )




async def mark_debt_as_paid(debt_id: int, db_session: AsyncSession) -> None:
    stmt = update(Debt).where(Debt.id == debt_id).values(is_paid=True)
    await db_session.execute(stmt)


async def get_debt_by_id(debt_id: int, db_session: AsyncSession) -> Debt:
    query = select(Debt).where(Debt.id == debt_id)
    result = await db_session.execute(query)
    return result.unique().scalar_one()


async def mark_debt_as_unpaid(debt_id: int, db_session: AsyncSession) -> None:
    stmt = (
        update(Debt)
        .where(Debt.id == debt_id)
        .values(is_paid=False, paid_at=datetime.now(settings.bot.TIMEZONE))
    )
    await db_session.execute(stmt)
