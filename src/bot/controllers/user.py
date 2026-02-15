import logging

from aiogram.types import User as AiogramUser
from sqlalchemy import Result, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.internal.lexicon import ORDER, SETTINGS_QUESTIONS
from database.models import Record, User

logger = logging.getLogger(__name__)


async def add_user_to_db(
    user: AiogramUser, db_session: AsyncSession, is_admin: bool = False
) -> User:
    new_user = User(
        id=user.id, fullname=user.full_name, username=user.username, is_admin=is_admin
    )
    db_session.add(new_user)
    await db_session.flush()
    logger.info(f"New user created: {new_user}")
    return new_user


async def get_user_from_db_by_tg_id(
    telegram_id: int, db_session: AsyncSession
) -> User | None:
    query = select(User).filter(User.id == telegram_id)
    result: Result = await db_session.execute(query)
    user = result.unique().scalar_one_or_none()
    return user


async def get_all_users(db_session: AsyncSession) -> list[User]:
    query = select(User)
    result: Result = await db_session.execute(query)
    return list(result.unique().scalars().all())


async def get_non_admin_users(
    db_session: AsyncSession, exclude_ids: set[int] | None = None
) -> list[User]:
    query = select(User).where(User.is_admin.is_(False))
    if exclude_ids:
        query = query.where(~User.id.in_(exclude_ids))
    query = query.order_by(User.fullname)
    result: Result = await db_session.execute(query)
    return list(result.unique().scalars().all())


async def get_last_played_users(db_session: AsyncSession) -> list[int]:
    query = select(User.id).where(User.last_time_played)
    result: Result = await db_session.execute(query)
    return list(result.unique().scalars().all())


async def get_players_from_game(game_id: int, db_session: AsyncSession) -> list[User]:
    query = (
        select(User)
        .join(Record, User.id == Record.user_id)
        .where(Record.game_id == game_id)
    )
    result = await db_session.execute(query)
    return list(result.unique().scalars().all())


async def get_unplayed_users(db_session: AsyncSession) -> list[User]:
    query = select(User).where(~User.last_time_played)
    result: Result = await db_session.execute(query)
    return list(result.unique().scalars().all())


async def get_users_with_buyout(game_id: int, db_session: AsyncSession) -> list[User]:
    query = (
        select(User)
        .join(Record, User.id == Record.user_id)
        .where(Record.game_id == game_id, Record.buy_out.isnot(0))
    )
    result = await db_session.execute(query)
    return list(result.unique().scalars().all())


async def ask_next_question(user: User) -> tuple:
    for field in ORDER:
        if getattr(user, field) is None:
            question = SETTINGS_QUESTIONS[field]
            return field, question
    return None, None
