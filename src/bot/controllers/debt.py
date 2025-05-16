from datetime import datetime

from aiogram.types import CallbackQuery
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.controllers.user import get_user_from_db_by_tg_id
from bot.internal.lexicon import texts
from bot.internal.schemas import DebtData
from bot.internal.keyboards import get_paid_button
from database.models import Debt, User


async def get_debts(game_id, db_session):
    debts = select(Debt).filter(Debt.game_id == game_id)
    result = await db_session.execute(debts)
    debts = result.unique().scalars().all()
    return debts


def equalizer(balance_map: dict[int, int], game_id: int) -> list[DebtData]:
    pairs = [(user, amount) for user, amount in balance_map.items() if amount != 0]
    if not pairs:
        return []

    pairs.sort(key=lambda x: x[1])
    users, balances = zip(*pairs)
    balances = list(balances)

    min_result: list[DebtData] = []

    def dfs(start: int, current: list[int], path: list[DebtData]):
        nonlocal min_result

        while start < len(current) and current[start] == 0:
            start += 1

        if start == len(current):
            if not min_result or len(path) < len(min_result):
                min_result = list(path)
            return

        for i in range(start + 1, len(current)):
            if current[start] * current[i] < 0:
                amount = min(abs(current[start]), abs(current[i]))
                new = current[:]
                new[start] += amount if current[start] < 0 else -amount
                new[i] += amount if current[i] < 0 else -amount

                debtor, creditor = (
                    (users[start], users[i])
                    if current[start] < 0
                    else (users[i], users[start])
                )
                path.append(DebtData(game_id, creditor, debtor, amount))
                dfs(start + 1, new, path)
                path.pop()

    dfs(0, balances, [])
    return min_result


async def flush_debts_to_db(
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
        requisites = all((creditor.bank, creditor.IBAN, creditor.name_surname))
        debtor_text = texts["debtor_personal_game_report_with_requisites"].format(
            debt.game_id,
            debt.id,
            debt.amount / 100,
            creditor_username,
            creditor.bank,
            creditor.IBAN,
            creditor.name_surname,
        ) if requisites else texts["debtor_personal_game_report"].format(
            debt.game_id, debt.id, debt.amount / 100, creditor_username
        )
        msg = await callback.bot.send_message(
            chat_id=debtor.id,
            text=debtor_text,
            reply_markup=await get_paid_button(debt.id, debtor.id),
        )
        debt.debt_message_id = msg.message_id
        db_session.add(debt)
        await db_session.flush()
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
    from bot.config import settings

    stmt = (
        update(Debt)
        .where(Debt.id == debt_id)
        .values(is_paid=False, paid_at=datetime.now(settings.bot.TIMEZONE))
    )
    await db_session.execute(stmt)
