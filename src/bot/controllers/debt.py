from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.internal.schemas import DebtData
from database.models import Debt


async def get_debts(game_id: int, db_session: AsyncSession) -> list[Debt]:
    query = select(Debt).filter(Debt.game_id == game_id)
    result = await db_session.execute(query)
    return list(result.unique().scalars().all())


async def get_debts_with_users(game_id: int, db_session: AsyncSession) -> list[Debt]:
    query = (
        select(Debt)
        .filter(Debt.game_id == game_id)
        .options(selectinload(Debt.creditor), selectinload(Debt.debtor))
    )
    result = await db_session.execute(query)
    return list(result.unique().scalars().all())


def calculate_debt_amount(amount: int, ratio: int) -> Decimal:
    value = (Decimal(amount) * Decimal(ratio)) / Decimal(100)
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def equalizer(balance_map: dict[int, int], game_id: int) -> list[DebtData]:
    pairs = [(user, amount) for user, amount in balance_map.items() if amount != 0]
    if not pairs:
        return []

    pairs.sort(key=lambda x: x[1])
    users, balances = zip(*pairs, strict=True)
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
                dfs(start, new, path)
                path.pop()

    dfs(0, balances, [])
    return min_result


async def flush_debts_to_db(transactions: list[Debt], db_session: AsyncSession) -> None:
    for transaction in transactions:
        db_session.add(transaction)
    await db_session.flush()


async def mark_debt_as_paid(debt_id: int, db_session: AsyncSession) -> None:
    stmt = update(Debt).where(Debt.id == debt_id).values(is_paid=True)
    await db_session.execute(stmt)


async def get_debt_by_id(debt_id: int, db_session: AsyncSession) -> Debt | None:
    return await db_session.get(Debt, debt_id)


async def get_unpaid_debts_as_debtor(
    user_id: int, db_session: AsyncSession
) -> list[Debt]:
    """Get unpaid debts where user is the debtor (owes money to others)."""
    query = (
        select(Debt)
        .filter(
            Debt.debtor_id == user_id,
            or_(Debt.is_paid.is_(False), Debt.paid_at.is_(None)),
        )
        .options(selectinload(Debt.creditor), selectinload(Debt.game))
    )
    result = await db_session.execute(query)
    return list(result.unique().scalars().all())


async def get_unpaid_debts_as_creditor(
    user_id: int, db_session: AsyncSession
) -> list[Debt]:
    """Get unpaid debts where user is the creditor (others owe money to user)."""
    query = (
        select(Debt)
        .filter(
            Debt.creditor_id == user_id,
            or_(Debt.is_paid.is_(False), Debt.paid_at.is_(None)),
        )
        .options(selectinload(Debt.debtor), selectinload(Debt.game))
    )
    result = await db_session.execute(query)
    return list(result.unique().scalars().all())
