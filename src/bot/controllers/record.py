import logging

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql.functions import coalesce, func

from bot.controllers.debt import equalizer
from bot.internal.context import Amount, RecordUpdateMode
from bot.internal.schemas import GameBalanceData
from database.models import Debt, Record


logger = logging.getLogger(__name__)


async def create_record(game_id: int, user_id: int, db_session: AsyncSession) -> Record:
    new_record = Record(game_id=game_id, user_id=user_id)
    db_session.add(new_record)
    await db_session.flush()
    logger.info(
        f"New record added to game {game_id}: {new_record.id=}, {new_record.user_id=}"
    )
    return new_record


async def get_record(game_id: int, user_id: int, db_session: AsyncSession) -> Record:
    query = select(Record).filter(Record.game_id == game_id, Record.user_id == user_id)
    result = await db_session.execute(query)
    return result.unique().scalar_one()

async def update_record(
    game_id: int,
    user_id: int,
    mode: RecordUpdateMode,
    value: int,
    db_session: AsyncSession,
) -> Record:
    query = select(Record).filter(Record.game_id == game_id, Record.user_id == user_id)
    result = await db_session.execute(query)
    record = result.unique().scalar_one_or_none()
    field = "buy in" if mode == RecordUpdateMode.UPDATE_BUY_IN else "buy out"
    match mode:
        case RecordUpdateMode.UPDATE_BUY_IN:
            record.buy_in = value
        case RecordUpdateMode.UPDATE_BUY_OUT:
            record.buy_out = value
    await db_session.flush()
    logger.info(f"Game {game_id}. Update {field} to {value} for user {user_id}")
    return record


async def increase_player_buy_in(
    user_id: int, game_id: int, amount: Amount, db_session: AsyncSession
) -> None:
    query = (
        update(Record)
        .where(Record.user_id == user_id, Record.game_id == game_id)
        .values(buy_in=(coalesce(Record.buy_in, 0) + amount.value))
    )
    await db_session.execute(query)


async def get_remained_players_in_game(game_id: int, db_session: AsyncSession) -> str:
    query = (
        select(Record)
        .where(Record.game_id == game_id, Record.buy_out.is_(None))
        .options(selectinload(Record.user))
    )
    result = await db_session.execute(query)
    records = result.unique().scalars().all()
    remaining_players = [record.user for record in records]
    remaining_players_names = []
    if remaining_players:
        for player in remaining_players:
            remaining_players_names.append(player.fullname)
    return ", ".join(remaining_players_names)


async def check_game_balance(game_id: int, db_session: AsyncSession) -> GameBalanceData:
    total_pot_query = select(func.sum(Record.buy_in).filter(Record.game_id == game_id))
    total_buy_outs_query = select(
        func.sum(Record.buy_out).filter(Record.game_id == game_id)
    )
    total_pot_result = await db_session.execute(total_pot_query)
    total_buy_outs_result = await db_session.execute(total_buy_outs_query)
    total_pot = total_pot_result.scalar_one_or_none()
    total_buy_outs = total_buy_outs_result.scalar_one_or_none()
    if total_pot is None or total_buy_outs is None:
        return GameBalanceData(None, None)
    delta = total_pot - total_buy_outs
    results = GameBalanceData(total_pot, delta)
    return results


async def debt_calculator(game_id: int, db_session: AsyncSession) -> list[Debt]:
    records_query = select(Record).filter(Record.game_id == game_id)
    records_result = await db_session.execute(records_query)
    records = records_result.unique().scalars().all()

    balance_map = {}
    for record in records:
        amount = 0 if record.net_profit is None else int(record.net_profit)
        if amount != 0:
            balance_map[record.user_id] = amount

    return [debt.to_model() for debt in equalizer(balance_map, game_id)]


async def update_net_profit_and_roi(game_id: int, db_session: AsyncSession):
    stmt = (
        select(Record)
        .where(Record.game_id == game_id)
        .options(selectinload(Record.user))
    )

    result = await db_session.execute(stmt)
    records = result.unique().scalars().all()

    for record in records:
        if record.buy_in is not None and record.buy_out is not None:
            record.net_profit = record.buy_out - record.buy_in
            if record.buy_in > 0:
                roi = (record.net_profit / record.buy_in) * 100
                record.ROI = round(roi, 2)
            else:
                record.ROI = None
            db_session.add(record)
    await db_session.flush()


async def get_mvp(game_id: int, db_session: AsyncSession):
    query = (
        select(Record.user_id)
        .filter(Record.game_id == game_id)
        .order_by(Record.ROI.desc())
        .limit(1)
    )
    result = await db_session.execute(query)
    mvp = result.scalar_one_or_none()
    return mvp


async def get_roi_from_game_by_player_id(
    game_id: int, player_id: int, db_session: AsyncSession
):
    query = select(Record.ROI).where(
        Record.game_id == game_id, Record.user_id == player_id
    )
    result = await db_session.execute(query)
    record = result.scalar()
    return record
